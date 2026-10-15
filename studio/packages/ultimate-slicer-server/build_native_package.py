"""Create an offline, version-neutral native-slicer source bundle.

Private preparation only: the bundle is NOT an installable/release-approved package
until Linux path separation, signed engine provenance and root installer are tested.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

NAME = "ultimate-slicer-server"
LINE = re.compile(r"(?P<hash>[0-9a-f]{64})  (?P<path>[a-zA-Z0-9_.\-/]+)\Z")
HOST_MANIFEST_EXPECTED = {
    "server.py", "dispatch-job.sh", "progress-pipe-reader.py",
    "refresh-state.sh", "append-slicing-journal.sh",
    "bambu_lab_h2s_04.json",
    "profiles/printers/bambu_lab_a1_04.json",
    "profiles/printers/bambu_lab_h2s_04.json",
    "systemd/3d-printer-slicing-server.service",
    "systemd/3d-printer-slicing-dispatch.service",
    "systemd/3d-printer-slicing-dispatch.timer",
    "systemd/3d-printer-slicing-refresh.service",
    "systemd/3d-printer-slicing-refresh.timer",
}
NATIVE_UNITS_EXPECTED = {
    "ultimate-slicer-server.service",
    "ultimate-slicer-dispatch.service",
    "ultimate-slicer-dispatch.timer",
    "ultimate-slicer-refresh.service",
    "ultimate-slicer-refresh.timer",
}

DEPENDENCIES_EXPECTED = {
    "bed-temperature-contract.sh", "materialize-bambu-machine.py",
    "materialize-bambu-multimaterial.py", "three_mf_mesh_graph.py",
    "filament_parameter_contract.py", "native_filament_defaults.json",
    "slicer_execution_contract.py", "gcode_artifact_validation.py",
    "printer_model_contract.py", "h2s_native_defaults.json",
    "job_control.py",
}


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _manifest(path: Path, expected: set[str]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LINE.fullmatch(line)
        if match is None:
            raise ValueError("unrecognized source manifest syntax")
        name = match.group("path")
        rel = PurePosixPath(name)
        if rel.is_absolute() or name != rel.as_posix() or ".." in rel.parts or any(part.startswith(".") for part in rel.parts):
            raise ValueError("unsafe source filename in manifest")
        if name in rows:
            raise ValueError("duplicate source manifest filename")
        rows[name] = match.group("hash")
    if set(rows) != expected:
        raise ValueError("native package has a missing or unexpected source dependency")
    return rows


def _read_pinned(root: Path, relative: str, expected_hash: str) -> bytes:
    resolved_root = root.resolve(strict=True)
    source = root / relative
    resolved = source.resolve(strict=True)
    if not resolved.is_relative_to(resolved_root) or source.is_symlink() or not source.is_file():
        raise ValueError("package source not a regular file")
    content = source.read_bytes()
    if _digest(content) != expected_hash:
        raise ValueError("source SHA-256 not equal to reviewed native manifest")
    return content


def _add_bytes(tar: tarfile.TarFile, name: str, value: bytes, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(f"{NAME}/{name}")
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    info.size = len(value)
    info.mode = mode
    tar.addfile(info, io.BytesIO(value))


def build(root: Path, destination: Path) -> dict:
    host = root / "deploy" / "homeassistant" / "host" / "3d-printer-slicing-server"
    component = root / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"
    host_pins = _manifest(host / "SHA256SUMS", HOST_MANIFEST_EXPECTED)
    deps = _manifest(host / "DEPENDENCY-SHA256SUMS", DEPENDENCIES_EXPECTED)
    files: dict[str, bytes] = {}

    # Legacy systemd units are verified for provenance but explicitly not shipped.
    # They contain private HA host paths; independent units must be provided
    # and tested as a separate step.
    for relative, expected_hash in host_pins.items():
        content = _read_pinned(host, relative, expected_hash)
        if not relative.startswith("systemd/"):
            files[f"payload/{relative}"] = content
    for relative, expected_hash in deps.items():
        source = host if relative == "job_control.py" else component
        files[f"payload/{relative}"] = _read_pinned(source, relative, expected_hash)

    unit_root = Path(__file__).resolve().parent / "systemd"
    for name in sorted(NATIVE_UNITS_EXPECTED):
        unit_path = unit_root / name
        if unit_path.is_symlink() or not unit_path.is_file():
            raise ValueError("required independent systemd unit is missing or linked")
        unit = unit_path.read_bytes()
        if b"/var/lib/homeassistant" in unit or b"printer_control_center" in unit:
            raise ValueError("native unit references an unrelated Home Assistant runtime")
        if name.endswith(".service") and (
            b"User=ultimate-slicer" not in unit
            or b"ProtectSystem=strict" not in unit
            or b"NoNewPrivileges=yes" not in unit
        ):
            raise ValueError("native unit lacks unprivileged runtime safeguards")
        files[f"systemd/{name}"] = unit

    installer_path = Path(__file__).resolve().parent / "install_native.py"
    if installer_path.is_symlink() or not installer_path.is_file():
        raise ValueError("native first-install tool is missing or linked")
    files["installer/install_native.py"] = installer_path.read_bytes()
    release_path = Path(__file__).resolve().parent / "release.json"
    if release_path.is_symlink() or not release_path.is_file():
        raise ValueError("native release metadata missing or linked")
    release_bytes = release_path.read_bytes()
    try:
        release = json.loads(release_bytes)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("native release metadata invalid") from error
    if (
        not isinstance(release, dict)
        or not isinstance(release.get("version"), str)
        or not re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+(?:[-+][A-Za-z0-9.-]+)?", release["version"])
        or type(release.get("api_protocol")) is not int
        or release["api_protocol"] < 2
    ):
        raise ValueError("invalid native package release fields")
    files["payload/release.json"] = release_bytes

    expected_files = 8 + len(deps) + len(NATIVE_UNITS_EXPECTED) + 2
    if len(files) != expected_files:
        raise ValueError("unexpected independent native-slicer package closure")

    record = {
        "schema": 1,
        "package": NAME,
        "native_version": release["version"],
        "api_protocol": release["api_protocol"],
        "complete_source_file_count": len(files),
        "native_deploy_ready": False,
        "contains_private_configuration": False,
        "contains_slicer_engine_binary": False,
        "native_systemd_units_ready": True,
        "first_install_tool_included": True,
        "source_hashes_verified": True,
        "files": [
            {"path": key, "sha256": _digest(value), "size_bytes": len(value)}
            for key, value in sorted(files.items())
        ],
        "required_next_gates": [
            "Separate source and mutable state paths in all worker scripts",
            "Test first install, idempotent upgrade and rollback under Linux/root without HA",
            "Verify slicing engine license, provenance, executable and required profiles",
            "Test Debian native first install, upgrade and rollback without HA",
        ],
    }
    metadata = (json.dumps(record, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    files["source-manifest.json"] = metadata

    if destination.exists():
        raise FileExistsError("never overwrite a previous private bundle")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as raw, gzip.GzipFile(
        fileobj=raw, mode="wb", filename="", mtime=0
    ) as zipped, tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, value in sorted(files.items()):
            executable = name.endswith(".sh") or name.endswith("/progress-pipe-reader.py")
            _add_bytes(archive, name, value, 0o755 if executable else 0o644)

    return {
        "archive": str(destination),
        "archive_sha256": _digest(destination.read_bytes()),
        "bundle_file_count": len(files),
        "payload_file_count": len(files) - 1,
        "native_deploy_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source_root, args.output)
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
