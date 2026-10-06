"""Offline, data-only backup verification. Never restores into a live directory.

The inventory must come from an independent, frozen source snapshot. A matching
archive proves only that inventory's scope, not application/OS recoverability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
import unicodedata
import zipfile
import zlib
from pathlib import Path

CHUNK = 1024 * 1024
MAX_FILES = 100_000
MAX_BYTES = 64 * 1024**3
MAX_FILE_BYTES = 16 * 1024**3
MAX_MANIFEST_BYTES = 32 * 1024**2
HEX_SHA = re.compile(r"[0-9a-f]{64}\Z")
RESERVED = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.I)


class VerificationError(ValueError):
    """A machine-readable code, without file contents or private values."""


def safe_path(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise VerificationError("invalid_path")
    parts = value.split("/")
    if any(p in {"", ".", ".."} or p.endswith((".", " ")) or RESERVED.fullmatch(p) for p in parts):
        raise VerificationError("unsafe_path")
    if any(ord(c) < 32 or ord(c) == 127 or c in '\\:*?"<>|' for c in value):
        raise VerificationError("unsafe_path")
    if unicodedata.normalize("NFC", value) != value:
        raise VerificationError("noncanonical_path")
    return value


def digest(stream) -> str:
    result = hashlib.sha256()
    while data := stream.read(CHUNK):
        result.update(data)
    return result.hexdigest()


def file_record(path: Path) -> dict:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or path.is_symlink():
        raise VerificationError("snapshot_special_file")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        sha = digest(stream)
        after = os.fstat(stream.fileno())
    def identity(s):
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    final = path.lstat()
    # Compare each metadata API against itself. Some platforms expose different
    # timestamp precision through pathname stat and descriptor stat. Binding is
    # still checked with the file identity and size, never a timestamp tolerance.
    if (identity(before) != identity(final) or identity(opened) != identity(after)
            or not os.path.samestat(before, opened) or before.st_size != opened.st_size
            or not stat.S_ISREG(opened.st_mode) or not stat.S_ISREG(final.st_mode)):
        raise VerificationError("snapshot_changed")
    return {"size": after.st_size, "sha256": sha}


def _plain_directory(path: Path) -> Path:
    path = path.absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_dir():
        raise VerificationError("invalid_directory")
    return path


def validate_manifest(manifest: dict) -> dict:
    if not isinstance(manifest, dict) or type(manifest.get("format")) is not int or manifest["format"] != 1:
        raise VerificationError("invalid_manifest")
    files, roots = manifest.get("files"), manifest.get("required_roots")
    directories = manifest.get("directories")
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
        raise VerificationError("invalid_inventory")
    if not isinstance(roots, list) or not roots or any(not isinstance(r, str) for r in roots):
        raise VerificationError("missing_required_roots")
    if not isinstance(directories, list) or len(directories) > MAX_FILES:
        raise VerificationError("invalid_directories")
    folded, total = set(), 0
    for name in directories:
        safe_path(name)
        if name.casefold() in folded:
            raise VerificationError("path_collision")
        folded.add(name.casefold())
    for name, record in files.items():
        safe_path(name)
        if name.casefold() in folded:
            raise VerificationError("path_collision")
        folded.add(name.casefold())
        if not isinstance(record, dict) or type(record.get("size")) is not int:
            raise VerificationError("invalid_file_record")
        if not 0 <= record["size"] <= MAX_FILE_BYTES:
            raise VerificationError("file_size_limit")
        if not isinstance(record.get("sha256"), str) or not HEX_SHA.fullmatch(record["sha256"]):
            raise VerificationError("invalid_digest")
        total += record["size"]
    if total > MAX_BYTES:
        raise VerificationError("total_size_limit")
    names = set(files) | set(directories)
    for name in names:
        parts = name.split("/")
        if any("/".join(parts[:i]) not in directories for i in range(1, len(parts))):
            raise VerificationError("missing_parent_directory")
    normalized_roots = [safe_path(r) for r in roots]
    if len({r.casefold() for r in normalized_roots}) != len(roots):
        raise VerificationError("duplicate_required_root")
    for root in roots:
        if not any(name == root or name.startswith(root + "/") for name in names):
            raise VerificationError("required_root_missing")
    return {"format": 1, "files": files, "directories": directories, "required_roots": roots}


def inventory_snapshot(root: Path, required_roots: list[str]) -> dict:
    """Read a frozen snapshot, never an archive, to establish expected bytes."""
    root = _plain_directory(Path(root))
    files, directories = {}, []
    entries = sorted(root.rglob("*"))
    for path in entries:
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise VerificationError("snapshot_special_file")
        name = safe_path(path.relative_to(root).as_posix())
        if path.is_file():
            files[name] = file_record(path)
        else:
            directories.append(name)
    if entries != sorted(root.rglob("*")):
        raise VerificationError("snapshot_changed")
    for name, expected in files.items():
        if file_record(root / name) != expected:
            raise VerificationError("snapshot_changed")
    return validate_manifest({"format": 1, "files": files, "directories": directories, "required_roots": required_roots})


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError("duplicate_json_key")
        result[key] = value
    return result


def load_manifest(path: Path) -> dict:
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(data) > MAX_MANIFEST_BYTES:
        raise VerificationError("manifest_size_limit")
    try:
        return validate_manifest(json.loads(data, object_pairs_hook=_pairs))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError("invalid_manifest_json") from error


def _entries(raw):
    raw.seek(0)
    is_zip = zipfile.is_zipfile(raw)
    raw.seek(0)
    if is_zip:
        with zipfile.ZipFile(raw) as archive:
            if len(archive.infolist()) > MAX_FILES * 2:
                raise VerificationError("entry_count_limit")
            for item in archive.infolist():
                if item.orig_filename != item.filename:
                    raise VerificationError("noncanonical_archive_name")
                mode = item.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if item.flag_bits & 1 or kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise VerificationError("unsupported_archive_entry")
                if bool(item.is_dir()) != (kind == stat.S_IFDIR) and kind != 0:
                    raise VerificationError("inconsistent_entry_type")
                name = item.filename[:-1] if item.is_dir() else item.filename
                if item.is_dir():
                    if item.file_size:
                        raise VerificationError("directory_payload")
                    yield name, 0, None
                else:
                    with archive.open(item) as stream:
                        yield name, item.file_size, stream
    else:
        with tarfile.open(fileobj=raw, mode="r|*") as archive:
            for item in archive:
                if not (item.isfile() or item.isdir()) or item.issparse():
                    raise VerificationError("unsupported_archive_entry")
                name = item.name[:-1] if item.isdir() and item.name.endswith("/") else item.name
                if item.isdir():
                    if item.size:
                        raise VerificationError("directory_payload")
                    yield name, 0, None
                else:
                    with archive.extractfile(item) as stream:
                        yield name, item.size, stream


def verify_backup(archive_path: Path, manifest: dict, expected_archive_sha256: str,
                  scratch_parent: Path | None = None) -> dict:
    """Restore into a private temporary directory, re-read, then always remove it."""
    manifest = validate_manifest(manifest)
    if not isinstance(expected_archive_sha256, str) or not HEX_SHA.fullmatch(expected_archive_sha256):
        raise VerificationError("archive_digest_required")
    archive_path = Path(archive_path)
    if archive_path.is_symlink() or not archive_path.is_file():
        raise VerificationError("invalid_archive_file")
    parent = None
    if scratch_parent is not None:
        parent = _plain_directory(Path(scratch_parent))
        if any(parent.iterdir()):
            raise VerificationError("scratch_parent_not_empty")
    files = manifest["files"]
    total = sum(r["size"] for r in files.values())
    if shutil.disk_usage(parent or tempfile.gettempdir()).free < total + 16 * CHUNK:
        raise VerificationError("insufficient_scratch_space")
    seen, restored, count = set(), set(), 0
    try:
        with archive_path.open("rb") as raw:
            initial = os.fstat(raw.fileno())
            if initial.st_size > MAX_BYTES:
                raise VerificationError("archive_size_limit")
            if digest(raw) != expected_archive_sha256:
                raise VerificationError("archive_digest_mismatch")
            with tempfile.TemporaryDirectory(prefix="studio-restore-check-", dir=parent) as tmp:
                destination = Path(tmp)
                entries = _entries(raw)
                try:
                    for name, size, stream in entries:
                        count += 1
                        if count > MAX_FILES * 2:
                            raise VerificationError("entry_count_limit")
                        if stream is None and name in {".", "./"}:
                            if "" in seen:
                                raise VerificationError("duplicate_archive_path")
                            seen.add("")
                            continue
                        while name.startswith("./"):
                            name = name[2:]
                        safe_path(name)
                        if name.casefold() in seen:
                            raise VerificationError("duplicate_archive_path")
                        seen.add(name.casefold())
                        target = destination.joinpath(*name.split("/"))
                        if stream is None:
                            if name not in manifest["directories"]:
                                raise VerificationError("unlisted_archive_directory")
                            target.mkdir(parents=True, exist_ok=True)
                            continue
                        expected = files.get(name)
                        if expected is None:
                            raise VerificationError("unlisted_archive_file")
                        if size != expected["size"]:
                            raise VerificationError("file_size_mismatch")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        remaining, sha = size, hashlib.sha256()
                        with target.open("xb") as output:
                            while remaining:
                                data = stream.read(min(CHUNK, remaining))
                                if not data:
                                    raise VerificationError("truncated_entry")
                                output.write(data)
                                sha.update(data)
                                remaining -= len(data)
                            if stream.read(1):
                                raise VerificationError("excess_entry_data")
                        if sha.hexdigest() != expected["sha256"]:
                            raise VerificationError("file_digest_mismatch")
                        restored.add(name)
                finally:
                    entries.close()
                if restored != set(files):
                    raise VerificationError("missing_archive_file")
                actual_dirs = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_dir()}
                if actual_dirs != set(manifest["directories"]):
                    raise VerificationError("directory_set_mismatch")
                for name, expected in files.items():
                    if file_record(destination / name) != expected:
                        raise VerificationError("restored_file_mismatch")
                raw.seek(0)
                if digest(raw) != expected_archive_sha256 or any(getattr(os.fstat(raw.fileno()), field) != getattr(initial, field)
                    for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
                    raise VerificationError("archive_changed")
    except (OSError, tarfile.TarError, zipfile.BadZipFile, zlib.error, EOFError, RuntimeError) as error:
        raise VerificationError("archive_io_error") from error
    return {"success": True, "scope": "independent_manifest_only", "files_verified": len(files),
            "bytes_verified": total, "directories_verified": len(manifest["directories"]), "required_roots_verified": len(manifest["required_roots"]),
            "archive_sha256": expected_archive_sha256, "temporary_restore_removed": True,
            "live_restore_performed": False, "full_system_restore_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("inventory", help="Read an independent, frozen snapshot")
    capture.add_argument("snapshot", type=Path)
    capture.add_argument("--required-root", action="append", required=True)
    check = commands.add_parser("verify", help="Check TAR/ZIP data in a temporary directory")
    check.add_argument("archive", type=Path)
    check.add_argument("manifest", type=Path)
    check.add_argument("--archive-sha256", required=True)
    check.add_argument("--scratch-parent", type=Path)
    args = parser.parse_args()
    try:
        result = (inventory_snapshot(args.snapshot, args.required_root) if args.command == "inventory"
                  else verify_backup(args.archive, load_manifest(args.manifest), args.archive_sha256,
                                     args.scratch_parent))
    except (VerificationError, OSError) as error:
        code = str(error) if isinstance(error, VerificationError) else "input_io_error"
        print(json.dumps({"success": False, "error": code}))
        return 1
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
