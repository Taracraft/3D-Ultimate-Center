"""Prepare an explicit, verified Docker build context without executing a worker."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile

HOST = "deploy/homeassistant/host/3d-printer-slicing-server"
COMPONENT = "deploy/homeassistant/custom_components/ultimate_3d_studio"
HOST_FILES = (
    "server.py", "job_control.py", "dispatch-job.sh", "progress-pipe-reader.py",
    "refresh-state.sh", "append-slicing-journal.sh", "bambu_lab_h2s_04.json",
    "profiles/printers/bambu_lab_a1_04.json", "profiles/printers/bambu_lab_h2s_04.json",
)
COMPONENT_FILES = (
    "bed-temperature-contract.sh", "materialize-bambu-machine.py",
    "materialize-bambu-multimaterial.py", "three_mf_mesh_graph.py",
    "filament_parameter_contract.py", "native_filament_defaults.json",
    "slicer_execution_contract.py", "gcode_artifact_validation.py",
    "printer_model_contract.py", "h2s_native_defaults.json",
)
SUPPORT_FILES = ("Dockerfile", ".dockerignore", "container_check.py", "container_runtime.py", "container_probe.py", "container_service.py", "container_engines.py", "LICENSE", "THIRD_PARTY_NOTICES.md", "TARGET_IMAGE_REFERENCE.json", "target_image_sbom.py", "verify_profile_sources.py")
LICENSE_FILES = {
    "licenses/MIT-Studio.txt": ("2cd47d14537993c48a899d2a3e6b30cf764ea31e18a468b662263e1f14027708", "inherited-license-notice"),
    "licenses/AGPL-BambuStudio.txt": ("57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6", "third-party-license-notice"),
}
PROFILE_SOURCE_FILE = "PROFILE_SOURCE_BUNDLE.json"
PROFILE_SOURCE_SHA256 = "b7ecec0be50f76e4bb4ed85df68f88f28bc34ff34f42a754a3cbdddf9796fa1f"
LIMIT = 16 * 1024 * 1024

class ContextError(ValueError):
    pass

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_regular(root, relative):
    relative = PurePosixPath(relative)
    if relative.is_absolute() or not relative.parts or any(p in {"..", "."} for p in relative.parts):
        raise ContextError("invalid_relative_path")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ContextError("linked_source:" + relative.as_posix())
    before = current.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > LIMIT:
        raise ContextError("invalid_source:" + relative.as_posix())
    with current.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if not os.path.samestat(before, opened):
            raise ContextError("source_changed")
        data = stream.read(LIMIT + 1)
        after = os.fstat(stream.fileno())
    final = current.stat()
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    # Windows stat and fstat can report timestamps differently; compare each API with itself.
    if len(data) != before.st_size or identity(before) != identity(final) or identity(opened) != identity(after):
        raise ContextError("source_changed")
    return data

def checksum_map(data):
    result = {}
    for line in data.decode("utf-8-sig").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        if not match or match[2] in result:
            raise ContextError("invalid_source_manifest")
        result[match[2]] = match[1]
    return result

def collect(root):
    root = Path(root).absolute()
    if root.is_symlink() or getattr(root, "is_junction", lambda: False)():
        raise ContextError("linked_source_root")
    host_hashes = checksum_map(read_regular(root, HOST + "/SHA256SUMS"))
    dependency_hashes = checksum_map(read_regular(root, HOST + "/DEPENDENCY-SHA256SUMS"))
    payload, rows = {}, []
    for prefix, names in ((HOST, HOST_FILES), (COMPONENT, COMPONENT_FILES)):
        for name in names:
            source = prefix + "/" + name
            data = read_regular(root, source)
            expected = (dependency_hashes if prefix == COMPONENT or name == "job_control.py" else host_hashes).get(name)
            if not expected or digest(data) != expected:
                raise ContextError("source_digest_mismatch:" + name)
            target = "payload/" + name
            payload[target] = data
            rows.append({"path": target, "source": source, "sha256": digest(data), "size_bytes": len(data), "license_scope": "inherited-unresolved"})
    source = "packages/ultimate-slicer-server/release.json"
    release = read_regular(root, source)
    identity = json.loads(release.decode("utf-8-sig"))
    if not isinstance(identity, dict) or type(identity.get("api_protocol")) is not int or identity["api_protocol"] < 2:
        raise ContextError("invalid_release_metadata")
    if not isinstance(identity.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", identity["version"]):
        raise ContextError("invalid_release_metadata")
    payload["payload/release.json"] = release
    rows.append({"path": "payload/release.json", "source": source, "sha256": digest(release), "size_bytes": len(release), "license_scope": "inherited-unresolved"})
    for name in SUPPORT_FILES:
        data = read_regular(root, "Slicer-Server/" + name)
        payload[name] = data
        if name not in {"Dockerfile", ".dockerignore"}:
            rows.append({"path": name, "source": "Slicer-Server/" + name, "sha256": digest(data), "size_bytes": len(data), "license_scope": "own-new-material"})
    for name, (expected, scope) in LICENSE_FILES.items():
        data = read_regular(root, "Slicer-Server/" + name)
        if digest(data) != expected:
            raise ContextError("license_notice_digest_mismatch:" + name)
        payload[name] = data
        rows.append({"path": name, "source": "Slicer-Server/" + name,
                     "sha256": digest(data), "size_bytes": len(data), "license_scope": scope})
    name = "PAYLOAD_PROVENANCE.json"
    data = read_regular(root, "Slicer-Server/" + name)
    try:
        provenance = json.loads(data.decode("utf-8"))
        entries = provenance["payload_files"]
        expected_paths = set(payload) - set(LICENSE_FILES) - set(SUPPORT_FILES) - {"payload/release.json"}
        if (provenance["schema"] != 1 or provenance["publication_approved"] is not False
                or provenance["sources_are_not_relicensed"] is not True
                or not isinstance(entries, list) or len(entries) != len(expected_paths)
                or {entry["path"] for entry in entries} != expected_paths
                or any(entry["sha256"] != digest(payload[entry["path"]]) for entry in entries)):
            raise ValueError("provenance_binding_invalid")
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise ContextError("payload_provenance_mismatch") from exc
    payload[name] = data
    rows.append({"path": name, "source": "Slicer-Server/" + name,
                 "sha256": digest(data), "size_bytes": len(data), "license_scope": "provenance-notice"})
    data = read_regular(root, "Slicer-Server/" + PROFILE_SOURCE_FILE)
    if digest(data) != PROFILE_SOURCE_SHA256:
        raise ContextError("profile_source_bundle_digest_mismatch")
    payload[PROFILE_SOURCE_FILE] = data
    rows.append({"path": PROFILE_SOURCE_FILE, "source": "Slicer-Server/" + PROFILE_SOURCE_FILE,
                 "sha256": digest(data), "size_bytes": len(data),
                 "license_scope": "third-party-profile-source"})
    manifest = {
        "schema": 1, "package": "ultimate-slicer-server", "version": identity["version"],
        "api_protocol": identity["api_protocol"], "container_stage": "source-preflight",
        "container_deploy_ready": False, "engine_included": False,
        "sources_are_not_relicensed": True, "files": sorted(rows, key=lambda row: row["path"]),
        "open_acceptance": ["container-worker-isolation-and-lifecycle", "engine-and-profile-provenance",
                            "linux-container-build-and-install", "tls-and-ha-connection",
                            "upgrade-backup-and-restore", "license-scope-and-public-release"],
    }
    payload["context-manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    return payload, manifest

def prepare(root, output):
    root, output = Path(root).absolute(), Path(output).absolute()
    resolved_root, resolved_output = root.resolve(), output.resolve()
    if resolved_output == resolved_root or resolved_root in resolved_output.parents:
        raise ContextError("output_must_be_outside_source")
    if output.exists() or output.is_symlink():
        raise ContextError("output_already_exists")
    parent = output.parent
    if not parent.is_dir():
        raise ContextError("output_parent_missing")
    for entry in (parent, *parent.parents):
        if entry.is_symlink() or getattr(entry, "is_junction", lambda: False)():
            raise ContextError("linked_output_parent")
    payload, manifest = collect(root)
    # Reserve the final directory exclusively; never replace another caller's output.
    output.mkdir(mode=0o700)
    try:
        for relative, data in payload.items():
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
            target.chmod(0o644)
            if target.read_bytes() != data:
                raise ContextError("context_readback_mismatch")
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return {"context_created": True, "file_count": len(payload),
            "manifest_sha256": digest(payload["context-manifest.json"]),
            "container_deploy_ready": False, "engine_included": False,
            "source_files": len(manifest["files"])}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.source_root, args.output), sort_keys=True))
    except (ContextError, OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, ContextError) else type(exc).__name__
        parser.exit(1, "Docker context rejected: " + code + "\n")

if __name__ == "__main__":
    main()
