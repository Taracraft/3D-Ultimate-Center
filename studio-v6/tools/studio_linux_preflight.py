"""Validate/stage an allowlisted native Studio package; never install or start it.

Hashes prove correspondence with the supplied manifests, not their authenticity
or release approval. Keep this source tree at a reviewed, fixed revision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
from typing import Any

RUNTIME = (
    "bambu_lab_h2s_04.json", "server.py", "job_control.py", "dispatch-job.sh",
    "progress-pipe-reader.py", "refresh-state.sh", "append-slicing-journal.sh",
)
UNITS = tuple("3d-printer-slicing-" + name for name in (
    "server.service", "dispatch.service", "dispatch.timer", "refresh.service", "refresh.timer",
))
DEPENDENCIES = frozenset({
    "bed-temperature-contract.sh", "materialize-bambu-machine.py",
    "materialize-bambu-multimaterial.py", "three_mf_mesh_graph.py",
    "filament_parameter_contract.py", "native_filament_defaults.json",
    "slicer_execution_contract.py", "gcode_artifact_validation.py",
    "printer_model_contract.py", "h2s_native_defaults.json", "job_control.py",
})
PRIMARY_REQUIRED = frozenset(set(RUNTIME) - {"job_control.py"}) | frozenset("systemd/" + u for u in UNITS)
PRIMARY_ALLOWED = PRIMARY_REQUIRED | {"job_control.py"}
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_PACKAGE_BYTES = 64 * 1024 * 1024
FORBIDDEN_SOURCE_ENTRIES = frozenset({"config.json", "secrets.yaml", ".env", ".storage", "data", "run", "engines", "backups"})
LIVE_ROOTS = tuple(Path(p) for p in (
    "/var/lib/homeassistant/3d-printer-slicing-server",
    "/var/lib/homeassistant/homeassistant", "/etc/systemd/system",
))


class PreflightError(ValueError):
    """Stable error without file contents, credentials or absolute paths."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _version(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _link(path: Path, info: os.stat_result) -> bool:
    return (stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_reparse_tag", 0) & 0x20000000)
            or bool(getattr(path, "is_junction", lambda: False)()))


def _plain(path: Path, *, directory: bool) -> Path:
    path = Path(os.path.abspath(path))
    for parent in reversed(path.parents):
        info = parent.lstat()
        if _link(parent, info) or not stat.S_ISDIR(info.st_mode):
            raise PreflightError("linked_path")
    info = path.lstat()
    if _link(path, info):
        raise PreflightError("linked_path")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise PreflightError("invalid_file_type")
    return path


def _read(path: Path, maximum: int = MAX_FILE_BYTES) -> bytes:
    path = _plain(path, directory=False)
    before = path.lstat()
    if before.st_size > maximum:
        raise PreflightError("file_size_limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not os.path.samestat(before, opened) or not stat.S_ISREG(opened.st_mode):
            raise PreflightError("source_changed")
        data = stream.read(maximum + 1)
        if _version(opened) != _version(os.fstat(stream.fileno())):
            raise PreflightError("source_changed")
    if len(data) > maximum:
        raise PreflightError("file_size_limit")
    # Compare path and handle timestamps within their own APIs; on Windows their
    # ctime meanings are not interchangeable.
    if _version(before) != _version(path.lstat()) or len(data) != before.st_size:
        raise PreflightError("source_changed")
    return data


def _manifest(data: bytes, allowed: frozenset[str], required: frozenset[str]) -> dict[str, str]:
    if len(data) > MAX_MANIFEST_BYTES:
        raise PreflightError("manifest_size_limit")
    try:
        lines = data.decode("utf-8-sig").splitlines()
    except UnicodeError as exc:
        raise PreflightError("manifest_encoding") from exc
    result: dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64}) [ *]([A-Za-z0-9_.\-/]+)", line)
        if match is None or match[2] not in allowed:
            raise PreflightError("invalid_manifest_entry")
        if match[2] in result:
            raise PreflightError("duplicate_manifest_entry")
        result[match[2]] = match[1]
    if not required.issubset(result):
        raise PreflightError("incomplete_manifest:" + ",".join(sorted(required - result.keys())))
    return result


def _array(script: str, name: str, expected: tuple[str, ...]) -> None:
    matches = re.findall(r"(?m)^" + name + r"=\(\s*([^)]*)\)", script)
    try:
        actual = shlex.split(matches[0], comments=True) if len(matches) == 1 else []
    except ValueError as exc:
        raise PreflightError("unsupported_deployer_contract") from exc
    if actual != list(expected):
        raise PreflightError("unsupported_deployer_contract")


def collect(source_root: Path, layout: str) -> tuple[dict[str, bytes], list[Path]]:
    """Resolve only the two explicit source layouts; never use live dependencies."""
    root = _plain(source_root, directory=True)
    if layout == "public":
        native, units = root / "slicing-server", root / "deployment/systemd"
    elif layout == "canonical":
        native = root / "deploy/homeassistant/host/3d-printer-slicing-server"
        units = native / "systemd"
    else:
        raise PreflightError("unknown_layout")
    native, units = _plain(native, directory=True), _plain(units, directory=True)
    if any((native / name).exists() or (native / name).is_symlink() for name in FORBIDDEN_SOURCE_ENTRIES):
        raise PreflightError("runtime_data_in_source")
    primary_data = _read(native / "SHA256SUMS", MAX_MANIFEST_BYTES)
    dependency_data = _read(native / "DEPENDENCY-SHA256SUMS", MAX_MANIFEST_BYTES)
    primary = _manifest(primary_data, PRIMARY_ALLOWED, PRIMARY_REQUIRED)
    dependencies = _manifest(dependency_data, DEPENDENCIES, DEPENDENCIES)
    for name in primary.keys() & dependencies.keys():
        if primary[name] != dependencies[name]:
            raise PreflightError("conflicting_manifests")
    expected = {**primary, **dependencies}
    files = {"SHA256SUMS": primary_data, "DEPENDENCY-SHA256SUMS": dependency_data}
    locations = {"SHA256SUMS": native / "SHA256SUMS", "DEPENDENCY-SHA256SUMS": native / "DEPENDENCY-SHA256SUMS"}
    for name, digest in sorted(expected.items()):
        location = units / name.removeprefix("systemd/") if name.startswith("systemd/") else native / name
        data = _read(location)
        if _sha(data) != digest:
            raise PreflightError("source_digest_mismatch:" + name)
        files[name], locations[name] = data, location
    files["deploy-native-slicer.sh"] = _read(native / "deploy-native-slicer.sh")
    locations["deploy-native-slicer.sh"] = native / "deploy-native-slicer.sh"
    try:
        script = files["deploy-native-slicer.sh"].decode("utf-8-sig")
    except UnicodeError as exc:
        raise PreflightError("deployer_encoding") from exc
    _array(script, "RUNTIME_FILES", RUNTIME)
    _array(script, "UNIT_FILES", UNITS)
    if sum(map(len, files.values())) > MAX_PACKAGE_BYTES:
        raise PreflightError("package_size_limit")
    # Re-read every selected source, including both manifests and the deployer.
    for name, location in locations.items():
        if _read(location) != files[name]:
            raise PreflightError("source_changed")
    return files, [root, native, units]


def evidence(files: dict[str, bytes]) -> dict[str, Any]:
    entries = [{"path": name, "size_bytes": len(data), "sha256": _sha(data)} for name, data in sorted(files.items())]
    return {"schema": 1, "scope": "native_worker_source_package_only", "source_complete": True,
            "files": entries, "file_count": len(entries), "bytes": sum(item["size_bytes"] for item in entries),
            "package_sha256": _sha(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()),
            "installation_performed": False, "services_started": False, "release_approved": False,
            "remaining_requirements": ["full_release_source_and_quality_gate", "home_assistant_component_and_frontend",
                "native_bambu_engine_and_host_libraries", "private_configuration_and_authentication",
                "current_job_and_printer_state", "backup_rollback_and_live_acceptance"]}


def stage(source_root: Path, layout: str, destination: Path) -> dict[str, Any]:
    files, roots = collect(source_root, layout)
    destination = Path(os.path.abspath(destination))
    _plain(destination.parent, directory=True)
    if any(destination == root or destination.is_relative_to(root) for root in roots + list(LIVE_ROOTS)):
        raise PreflightError("unsafe_stage_destination")
    result = evidence(files)
    # Atomic reservation, not rename/replace: an existing empty directory is also
    # refused. Nothing at the destination is ever overwritten or recursively deleted.
    destination.mkdir(mode=0o700, exist_ok=False)
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _plain(target.parent, directory=True)
        with target.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        target.chmod(0o755 if name.endswith((".sh", ".py")) else 0o644)
        if _read(target) != data:
            raise PreflightError("stage_digest_mismatch")
    latest, _ = collect(source_root, layout)
    if latest != files:
        raise PreflightError("source_changed")
    if sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()) != sorted(files):
        raise PreflightError("stage_changed")
    # This completion record is written last. Failed staging leaves an explicitly
    # unapproved, incomplete directory for inspection; no cleanup touches live data.
    result.update(stage_complete=True)
    with (destination / "STAGING-MANIFEST.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--layout", choices=("public", "canonical"), required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Only read and validate the selected source package")
    mode.add_argument("--stage", type=Path, help="Create a NEW directory outside source/live roots; does not install")
    args = parser.parse_args(argv)
    try:
        result = evidence(collect(args.source_root, args.layout)[0]) if args.check else stage(args.source_root, args.layout, args.stage)
    except (PreflightError, OSError) as exc:
        code = str(exc) if isinstance(exc, PreflightError) else "input_or_stage_io_error"
        print(json.dumps({"success": False, "error": code, "installation_performed": False, "release_approved": False}))
        return 1
    print(json.dumps({"success": True, **result}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
