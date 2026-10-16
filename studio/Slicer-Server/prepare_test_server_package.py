"""Build a deterministic, secret-free package for the isolated Linux test server."""
from __future__ import annotations

import argparse
from gzip import GzipFile
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile


def _sibling(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, Path(__file__).with_name(filename))
    if spec is None or spec.loader is None:
        raise RuntimeError("dependency_loader_unavailable")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


context = _sibling("studio_test_package_context", "prepare_context.py")
verifier = _sibling("studio_test_package_verifier", "verify_test_server_package.py")

ARCHIVE_NAME = verifier.ARCHIVE_NAME
VERIFIER_NAME = verifier.VERIFIER_NAME
SUMS_NAME = verifier.SUMS_NAME
ROOT_NAME = verifier.ROOT_NAME
MANIFEST_NAME = verifier.MANIFEST_NAME

PACKAGE_FILES = (
    "Slicer-Server/clean_host_preflight.py",
    "Slicer-Server/compose.candidate.yaml",
    "Slicer-Server/LINUX_SETUP.md",
    "Slicer-Server/CONTAINER_TESTING.md",
    "Slicer-Server/RUNTIME_INSTALLATION.md",
    "Slicer-Server/OPERATIONS.md",
    "Slicer-Server/linux_test_evidence.py",
    "Slicer-Server/verify_test_server_package.py",
)

OPEN_ACCEPTANCE = (
    "real-clean-linux-host-preflight-and-compose-validation",
    "home-assistant-supervisor-integration",
    "cross-host-tls-and-secret-handling",
    "container-and-host-restart-persistence",
    "real-upgrade-rollback-backup-and-restore",
    "engine-license-and-provenance-closure",
    "fresh-hacs-installation-private-pilot-and-public-release",
)


class BuildError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mode(path: str) -> int:
    return 0o555 if path.endswith(".py") else 0o444


def collect(source_root: Path) -> tuple[dict[str, bytes], dict]:
    source_root = Path(source_root).absolute()
    context_payload, context_manifest = context.collect(source_root)
    if context_manifest["container_deploy_ready"] is not False or context_manifest["engine_included"] is not False:
        raise BuildError("context_release_flag_rejected")
    payload: dict[str, bytes] = {}
    for relative, data in context_payload.items():
        target = "context/" + PurePosixPath(relative).as_posix()
        payload[target] = data
    for relative in PACKAGE_FILES:
        target = PurePosixPath(relative).name
        if target in payload:
            raise BuildError("duplicate_package_target")
        payload[target] = context.read_regular(source_root, relative)
    rows = []
    for relative in sorted(payload):
        data = payload[relative]
        verifier._secret_free(data)
        rows.append(
            {
                "path": relative,
                "size_bytes": len(data),
                "sha256": digest(data),
                "mode": _mode(relative),
            }
        )
    manifest = {
        "schema": 1,
        "package": "ultimate-slicer-testserver",
        "archive_root": ROOT_NAME,
        "container_stage": "linux-testserver-candidate",
        "container_deploy_ready": False,
        "engine_included": False,
        "secret_files_included": False,
        "files": rows,
        "open_acceptance": list(OPEN_ACCEPTANCE),
    }
    payload[MANIFEST_NAME] = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    return payload, manifest


def _directory_names(payload: dict[str, bytes]) -> list[str]:
    result = {ROOT_NAME}
    for relative in payload:
        full = PurePosixPath(ROOT_NAME) / PurePosixPath(relative)
        for parent in full.parents:
            if parent.as_posix() == ".":
                break
            result.add(parent.as_posix())
    return sorted(result, key=lambda value: (len(PurePosixPath(value).parts), value))


def archive_bytes(payload: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for directory in _directory_names(payload):
            info = tarfile.TarInfo(directory)
            info.type = tarfile.DIRTYPE
            info.mode = 0o555
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info)
        for relative in sorted(payload):
            data = payload[relative]
            info = tarfile.TarInfo(f"{ROOT_NAME}/{relative}")
            info.size = len(data)
            info.mode = _mode(relative)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with GzipFile(filename="", mode="wb", fileobj=compressed, compresslevel=9, mtime=0) as stream:
        stream.write(raw.getvalue())
    return compressed.getvalue()


def _write_new(path: Path, data: bytes, mode: int) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(mode)
    if path.read_bytes() != data:
        raise BuildError("artifact_readback_mismatch:" + path.name)


def build(source_root: Path, output: Path) -> dict:
    source_root = Path(source_root).absolute()
    output = Path(output).absolute()
    resolved_source = source_root.resolve()
    resolved_output = output.resolve()
    if resolved_output == resolved_source or resolved_source in resolved_output.parents:
        raise BuildError("output_must_be_outside_source")
    if output.exists() or output.is_symlink():
        raise BuildError("output_already_exists")
    if not output.parent.is_dir():
        raise BuildError("output_parent_missing")
    for entry in (output.parent, *output.parent.parents):
        if entry.is_symlink() or getattr(entry, "is_junction", lambda: False)():
            raise BuildError("linked_output_parent")
    payload, manifest = collect(source_root)
    archive = archive_bytes(payload)
    verifier_data = payload[VERIFIER_NAME]
    sums = (
        f"{digest(archive)}  {ARCHIVE_NAME}\n"
        f"{digest(verifier_data)}  {VERIFIER_NAME}\n"
    ).encode("ascii")
    output.mkdir(mode=0o700)
    try:
        _write_new(output / ARCHIVE_NAME, archive, 0o444)
        _write_new(output / VERIFIER_NAME, verifier_data, 0o555)
        _write_new(output / SUMS_NAME, sums, 0o444)
        checked = verifier.verify_package_dir(output)
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return {
        "package_created": True,
        "output": str(output),
        "archive_sha256": digest(archive),
        "verifier_sha256": digest(verifier_data),
        "manifest_sha256": digest(payload[MANIFEST_NAME]),
        "archive_bytes": len(archive),
        "files": len(manifest["files"]),
        "sidecar_verified": checked["sidecar_verified"],
        "container_deploy_ready": False,
        "engine_included": False,
        "secret_files_included": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.source_root, args.output), sort_keys=True))
        return 0
    except (BuildError, context.ContextError, verifier.PackageError, OSError, ValueError) as exc:
        if isinstance(exc, (BuildError, context.ContextError, verifier.PackageError)):
            code = str(exc)
        else:
            code = type(exc).__name__
        parser.exit(1, "Test package build rejected: " + code + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
