"""Verify and optionally extract the deterministic Linux test-server package."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
from urllib.parse import urlsplit

ARCHIVE_NAME = "ultimate-slicer-testserver.tar.gz"
VERIFIER_NAME = "verify_test_server_package.py"
SUMS_NAME = "SHA256SUMS"
ROOT_NAME = "ultimate-slicer-testserver"
MANIFEST_NAME = "testserver-manifest.json"
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_FILES = 256


class PackageError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _regular_bytes(path: Path, limit: int) -> bytes:
    if path.is_symlink():
        raise PackageError("linked_package_file")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise PackageError("invalid_package_file")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if not os.path.samestat(before, opened):
            raise PackageError("package_file_changed")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    final = path.stat()
    identity = lambda value: (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if len(data) != before.st_size or identity(before) != identity(final) or identity(opened) != identity(after):
        raise PackageError("package_file_changed")
    return data


def _canonical_relative(value: str) -> str:
    if not isinstance(value, str) or not value or any(char in value for char in ("\\", ":", "\x00")):
        raise PackageError("invalid_manifest_path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PackageError("invalid_manifest_path")
    if path.as_posix() != value:
        raise PackageError("noncanonical_manifest_path")
    return value



# Reviewed documentation/schema origins in the deterministic source package.
# Changes to this set require a source review; no DNS/network lookup is used.
PUBLIC_PACKAGE_ORIGINS = frozenset({
    ("https", "github.com"),
    ("https", "opensource.org"),
    ("https", "docs.github.com"),
    ("https", "docs.docker.com"),
    ("http", "schemas.microsoft.com"),
    ("http", "www.gnu.org"),
    ("http", "fsf.org"),
})


def _example_hostname(host: str) -> bool:
    return host.endswith(".example") and re.fullmatch(
        r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+example", host
    ) is not None


def _public_network_references(data: bytes) -> None:
    # Inspect HTTP(S) references as data, never fetch them.
    for match in re.finditer(rb"https?://[^\s<>\"'\x60\\]*", data, re.IGNORECASE):
        if data[match.end():match.end() + 1] == b"\\":
            raise PackageError("private_domain_rejected")
        raw = match[0].rstrip(b"),.;]")
        try:
            parsed = urlsplit(raw.decode("ascii"))
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except (UnicodeDecodeError, ValueError) as exc:
            raise PackageError("private_domain_rejected") from exc
        scheme = parsed.scheme.lower()
        default_port = 443 if scheme == "https" else 80
        approved = (scheme, host) in PUBLIC_PACKAGE_ORIGINS or (
            scheme == "https" and _example_hostname(host)
        )
        if (
            not approved
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, default_port}
            or parsed.query
        ):
            raise PackageError("private_domain_rejected")
    # A standalone hostname line is also an explicit network reference.
    # Prose and arbitrary source identifiers still require public content review.
    public_hosts = {host for _, host in PUBLIC_PACKAGE_ORIGINS}
    for line in data.splitlines():
        token = line.strip().lower().rstrip(b".")
        if re.fullmatch(rb"(?:[a-z0-9-]+\.)+[a-z]{2,63}", token):
            host = token.decode("ascii")
            if host not in public_hosts and not _example_hostname(host):
                raise PackageError("private_domain_rejected")


def _secret_free(data: bytes) -> None:
    markers = (
        b"-----BEGIN " + b"PRIVATE KEY-----",
        b"-----BEGIN RSA " + b"PRIVATE KEY-----",
        b"-----BEGIN EC " + b"PRIVATE KEY-----",
        b"-----BEGIN OPENSSH " + b"PRIVATE KEY-----",
    )
    if any(marker in data for marker in markers):
        raise PackageError("private_key_material_rejected")
    if re.search(rb"(?<![A-Z0-9])AKIA[A-Z0-9]{16}(?![A-Z0-9])", data):
        raise PackageError("cloud_credential_pattern_rejected")
    if re.search(rb"(?<![A-Za-z0-9])(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}", data):
        raise PackageError("github_credential_pattern_rejected")
    if re.search(rb"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{20,}", data):
        raise PackageError("github_credential_pattern_rejected")
    _public_network_references(data)

    # Internal host references are private even when no credential is present.
    # Match host-label boundaries, not public example domains or prose.
    if re.search(
        rb"(?<![a-z0-9_.-])(?:[a-z0-9-]+\.)+(?:internal|local)\.?(?![a-z0-9_.-])",
        data,
        re.IGNORECASE,
    ):
        raise PackageError("private_domain_rejected")


def _member_name(member: tarfile.TarInfo) -> str:
    name = member.name.rstrip("/") if member.isdir() else member.name
    if any(char in name for char in ("\\", ":", "\x00")):
        raise PackageError("unsafe_archive_path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PackageError("unsafe_archive_path")
    if path.as_posix() != name:
        raise PackageError("noncanonical_archive_path")
    if not path.parts or path.parts[0] != ROOT_NAME:
        raise PackageError("unexpected_archive_root")
    return name


def _manifest(data: bytes) -> tuple[dict, dict[str, dict]]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError("invalid_package_manifest") from exc
    expected_keys = {
        "schema",
        "package",
        "archive_root",
        "container_stage",
        "container_deploy_ready",
        "engine_included",
        "secret_files_included",
        "files",
        "open_acceptance",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise PackageError("invalid_package_manifest")
    if value["schema"] != 1 or value["package"] != "ultimate-slicer-testserver":
        raise PackageError("invalid_package_manifest")
    if value["archive_root"] != ROOT_NAME or value["container_stage"] != "linux-testserver-candidate":
        raise PackageError("invalid_package_manifest")
    if value["container_deploy_ready"] is not False or value["engine_included"] is not False:
        raise PackageError("release_flag_rejected")
    if value["secret_files_included"] is not False:
        raise PackageError("secret_flag_rejected")
    if not isinstance(value["open_acceptance"], list) or not value["open_acceptance"]:
        raise PackageError("invalid_open_acceptance")
    rows = value["files"]
    if not isinstance(rows, list) or not rows or len(rows) > MAX_FILES:
        raise PackageError("invalid_manifest_files")
    mapped: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "size_bytes", "sha256", "mode"}:
            raise PackageError("invalid_manifest_row")
        path = _canonical_relative(row["path"])
        if path == MANIFEST_NAME or path in mapped:
            raise PackageError("duplicate_manifest_path")
        if type(row["size_bytes"]) is not int or not 0 <= row["size_bytes"] <= MAX_FILE_BYTES:
            raise PackageError("invalid_manifest_size")
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise PackageError("invalid_manifest_digest")
        if type(row["mode"]) is not int or row["mode"] not in {0o444, 0o555}:
            raise PackageError("invalid_manifest_mode")
        mapped[path] = row
    return value, mapped


def verify_archive(path: Path) -> dict:
    path = Path(path).absolute()
    _regular_bytes(path, MAX_ARCHIVE_BYTES)
    try:
        archive = tarfile.open(path, mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise PackageError("invalid_archive") from exc
    with archive:
        members = archive.getmembers()
        if not members or len(members) > MAX_FILES * 3:
            raise PackageError("invalid_archive_member_count")
        names: dict[str, tarfile.TarInfo] = {}
        for member in members:
            name = _member_name(member)
            if name in names:
                raise PackageError("duplicate_archive_member")
            if not (member.isdir() or member.isreg()):
                raise PackageError("archive_links_or_devices_rejected")
            if member.uid != 0 or member.gid != 0 or member.mtime != 0:
                raise PackageError("nondeterministic_archive_metadata")
            if member.uname or member.gname:
                raise PackageError("nondeterministic_archive_metadata")
            names[name] = member
        manifest_member = names.get(f"{ROOT_NAME}/{MANIFEST_NAME}")
        if manifest_member is None or not manifest_member.isreg() or manifest_member.size > 2 * 1024 * 1024:
            raise PackageError("package_manifest_missing")
        stream = archive.extractfile(manifest_member)
        if stream is None:
            raise PackageError("package_manifest_missing")
        manifest_data = stream.read(2 * 1024 * 1024 + 1)
        manifest, rows = _manifest(manifest_data)
        expected_files = {f"{ROOT_NAME}/{path}" for path in rows}
        expected_files.add(f"{ROOT_NAME}/{MANIFEST_NAME}")
        actual_files = {name for name, member in names.items() if member.isreg()}
        if actual_files != expected_files:
            raise PackageError("archive_file_set_mismatch")
        expected_dirs = {ROOT_NAME}
        for name in expected_files:
            path_value = PurePosixPath(name)
            for parent in path_value.parents:
                if parent.as_posix() == ".":
                    break
                expected_dirs.add(parent.as_posix())
        actual_dirs = {name for name, member in names.items() if member.isdir()}
        if actual_dirs != expected_dirs:
            raise PackageError("archive_directory_set_mismatch")
        for relative, row in rows.items():
            member = names[f"{ROOT_NAME}/{relative}"]
            if member.size != row["size_bytes"] or (member.mode & 0o777) != row["mode"]:
                raise PackageError("archive_metadata_mismatch:" + relative)
            stream = archive.extractfile(member)
            if stream is None:
                raise PackageError("archive_payload_missing:" + relative)
            data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) != row["size_bytes"] or digest(data) != row["sha256"]:
                raise PackageError("archive_digest_mismatch:" + relative)
            _secret_free(data)
        _secret_free(manifest_data)
    return {
        "verified": True,
        "archive_sha256": digest(_regular_bytes(path, MAX_ARCHIVE_BYTES)),
        "files": len(rows),
        "container_deploy_ready": manifest["container_deploy_ready"],
        "engine_included": manifest["engine_included"],
        "secret_files_included": manifest["secret_files_included"],
        "open_acceptance": manifest["open_acceptance"],
    }


def _checksum_map(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise PackageError("invalid_checksum_file") from exc
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if not match or match[2] in result:
            raise PackageError("invalid_checksum_file")
        result[match[2]] = match[1]
    if set(result) != {ARCHIVE_NAME, VERIFIER_NAME}:
        raise PackageError("invalid_checksum_file")
    return result


def verify_package_dir(path: Path) -> dict:
    root = Path(path).absolute()
    if root.is_symlink() or not root.is_dir():
        raise PackageError("invalid_package_directory")
    if {entry.name for entry in root.iterdir()} != {ARCHIVE_NAME, VERIFIER_NAME, SUMS_NAME}:
        raise PackageError("package_directory_file_set_mismatch")
    sums = _checksum_map(_regular_bytes(root / SUMS_NAME, 4096))
    for name, expected in sums.items():
        if digest(_regular_bytes(root / name, MAX_ARCHIVE_BYTES)) != expected:
            raise PackageError("package_sidecar_mismatch:" + name)
    result = verify_archive(root / ARCHIVE_NAME)
    result["sidecar_verified"] = True
    result["verifier_sha256"] = sums[VERIFIER_NAME]
    return result


def _remove_extraction(directories: set[Path], files: set[Path]) -> None:
    """Remove only paths created by this extraction; never ignore cleanup errors."""
    for directory in sorted(directories, key=lambda path: len(path.parts)):
        attributes = directory.lstat()
        if stat.S_ISLNK(attributes.st_mode) or (
            getattr(attributes, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise PackageError("extract_directory_changed")
        directory.chmod(0o700)
    for path in files:
        if not path.is_symlink():
            path.chmod(0o600)
        path.unlink()
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        directory.rmdir()


def extract_verified(archive_path: Path, output: Path) -> dict:
    verification = verify_archive(archive_path)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise PackageError("extract_target_exists")
    output.mkdir(mode=0o700)
    directories = {output}
    files: set[Path] = set()

    def ensure_directory(target: Path) -> None:
        current = output
        for part in target.relative_to(output).parts:
            current = current / part
            if current not in directories:
                current.mkdir(mode=0o700)
                directories.add(current)

    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                name = _member_name(member)
                relative = PurePosixPath(name).relative_to(ROOT_NAME)
                if not relative.parts:
                    continue
                target = output.joinpath(*relative.parts)
                if member.isdir():
                    ensure_directory(target)
                    continue
                ensure_directory(target.parent)
                stream = archive.extractfile(member)
                if stream is None:
                    raise PackageError("archive_payload_missing")
                data = stream.read(MAX_FILE_BYTES + 1)
                with target.open("xb") as writer:
                    files.add(target)
                    writer.write(data)
                    writer.flush()
                    os.fsync(writer.fileno())
                target.chmod(member.mode & 0o777)
                if _regular_bytes(target, MAX_FILE_BYTES) != data:
                    raise PackageError("extract_readback_mismatch")
        verify_extracted(output)
        # Keep the private outer root writable; protect children only after readback.
        for directory in sorted(directories - {output}, key=lambda path: len(path.parts), reverse=True):
            directory.chmod(0o555)
    except BaseException:
        try:
            _remove_extraction(directories, files)
        except (OSError, PackageError) as cleanup:
            raise PackageError("extract_cleanup_failed") from cleanup
        raise
    return {"extracted": True, "output": str(output), **verification}


def verify_extracted(root: Path) -> dict:
    root = Path(root).absolute()
    manifest_data = _regular_bytes(root / MANIFEST_NAME, 2 * 1024 * 1024)
    manifest, rows = _manifest(manifest_data)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual != set(rows) | {MANIFEST_NAME}:
        raise PackageError("extracted_file_set_mismatch")
    for relative, row in rows.items():
        path = root.joinpath(*PurePosixPath(relative).parts)
        data = _regular_bytes(path, MAX_FILE_BYTES)
        if len(data) != row["size_bytes"] or digest(data) != row["sha256"]:
            raise PackageError("extracted_digest_mismatch:" + relative)
        _secret_free(data)
    return {
        "verified": True,
        "files": len(rows),
        "container_deploy_ready": manifest["container_deploy_ready"],
        "engine_included": manifest["engine_included"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--package-dir", type=Path)
    group.add_argument("--archive", type=Path)
    group.add_argument("--extracted-root", type=Path)
    parser.add_argument("--extract", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.package_dir is not None:
            result = verify_package_dir(args.package_dir)
            archive_path = args.package_dir / ARCHIVE_NAME
        elif args.archive is not None:
            result = verify_archive(args.archive)
            archive_path = args.archive
        else:
            if args.extract is not None:
                raise PackageError("extract_requires_archive")
            result = verify_extracted(args.extracted_root)
            archive_path = None
        if args.extract is not None:
            result = extract_verified(archive_path, args.extract)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PackageError, OSError, tarfile.TarError) as exc:
        code = str(exc) if isinstance(exc, PackageError) else type(exc).__name__
        parser.exit(1, "Test package rejected: " + code + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
