"""Derive a Supervisor app build context from an independently pinned runtime.

No download, engine execution, Docker call, host configuration or approval.
The existing runtime verifier remains authoritative for all engine/source bytes.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

import prepare_runtime_context as runtime

dist = runtime.dist
APP_IMAGE = "ghcr.io/taracraft/ultimate-slicer-server-app"
RECEIPT = "app-context.json"
APP_FILES = ("supervisor_worker_policy.py", "supervisor_app_service.py")


class AppContextError(ValueError):
    pass


def require(value, code):
    if not value:
        raise AppContextError(code)


def configuration(version):
    require(type(version) is str and len(version) <= 64 and re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", version), "app_version_invalid")
    return {
        "name": "Ultimate Slicer Server", "version": version,
        "slug": "ultimate_slicer_server", "description": "Slicer API with an isolated non-networked worker",
        "url": "https://github.com/Taracraft/3D-Ultimate-Slicer-Server",
        "arch": ["amd64"], "image": APP_IMAGE, "startup": "services",
        "boot": "manual_only", "init": False, "stage": "experimental", "timeout": 90,
        "tmpfs": True, "host_network": False, "host_pid": False,
        "host_ipc": False, "host_dbus": False, "host_uts": False,
        "privileged": [], "apparmor": True, "hassio_api": False,
        "homeassistant_api": False, "docker_api": False, "auth_api": False,
        "ports": {"8099/tcp": None},
        "ports_description": {"8099/tcp": "HTTPS API; explicit host exposure only"},
        "map": [{"type": "ssl", "read_only": True}],
        "options": {"api_secret": "", "certfile": "server.crt", "keyfile": "server.key"},
        "schema": {"api_secret": "password", "certfile": "str", "keyfile": "str"},
    }


def dockerfile(raw, version):
    configuration(version)
    text = raw.decode("utf-8-sig")
    entry = 'ENTRYPOINT ["python3", "/' + runtime.IMAGE_BASE + '/runtime_image_check.py"]'
    require(text.count(entry) == 1 and text.count('CMD ["check"]') == 1
            and text.count("USER 65532:65532") == 1, "runtime_dockerfile_not_supported")
    lines = []
    for line in text.splitlines():
        if line.startswith("COPY "):
            parts = line.split()
            require(len(parts) >= 4 and parts[1] == "--chown=65532:65532",
                    "runtime_copy_not_supported")
            require(all(not name.startswith(("/", "..")) for name in parts[2:-1]),
                    "runtime_copy_not_supported")
            line = " ".join(parts[:2] + ["runtime/" + name for name in parts[2:-1]] + parts[-1:])
        lines.append(line)
    text = "\n".join(lines) + "\n"
    # Supervisor's rootfs may be writable. Neither the API nor worker may own
    # immutable code/engine files; runtime data are separate protected mounts.
    text = text.replace("USER 65532:65532", "USER 0:0\n"
        "RUN chown -R 0:0 /opt/ultimate-slicer-server /engine /usr/share/ultimate-slicer-server\n"
        'LABEL io.hass.type="addon" io.hass.arch="amd64" '
        'io.hass.name="Ultimate Slicer Server" io.hass.version="' + version + '"')
    text = text.replace(entry,
        'ENTRYPOINT ["python3", "-I", "/opt/ultimate-slicer-server/supervisor_app_service.py", "start"]')
    text = text.replace('CMD ["check"]', 'CMD []')
    return text.encode("utf-8")


def generated(root, pins):
    raw = dist.read_bounded(root / "source/context-manifest.json", runtime.LIMIT)
    manifest = runtime.image_check.document(raw)
    names = {row["path"] for row in manifest["files"]}
    require(set(APP_FILES) <= names, "app_sources_missing_from_runtime")
    version = manifest.get("version")
    config = dist.canonical(configuration(version))
    docker = dockerfile(dist.read_bounded(root / "Dockerfile", runtime.LIMIT), version)
    readme = ("# Ultimate Slicer Server app candidate\n\n"
        "This is a reproducible build context, not a published or installed app.\n"
        "Build with the independently reviewed PYTHON_BASE digest. The image name\n"
        "in config.json is a publication target, not proof that a tag exists.\n"
        "Do not register this folder as an app repository before image, sources,\n"
        "licenses, release metadata and safety review are actually complete.\n\n"
        "The app requires Linux/amd64 and Landlock ABI 6; unsupported kernels fail\n"
        "closed. It installs inherited default-deny seccomp filters itself, keeps\n"
        "worker network/IPC access blocked, and runs service processes as UID 65532\n"
        "with no capabilities. The short initial setup alone starts as root.\n"
        "Existing Compose isolation is unchanged; there is no automatic fallback.\n\n"
        "Configure a unique 32-256 character ASCII API secret and a matching TLS\n"
        "certificate/key in the standard read-only /ssl mount before manual start.\n"
        "The certificate must match the HTTPS hostname used by Home Assistant.\n"
        "No default host port is exposed, no Supervisor/Docker/HA API is granted,\n"
        "and boot is manual_only. Options are not exported or passed as secrets\n"
        "in command lines. Data/profiles and private controller files live in /data.\n"
        "A failed or unverified lifecycle retains its recovery record; do not delete\n"
        "that record as a substitute for investigating the failure.\n\n"
        "A context build does not execute an engine, submit a job, update Home\n"
        "Assistant or authorize a printer action. Unrun acceptance stays unrun.\n")
    result = {"Dockerfile": docker, "config.json": config,
              ".dockerignore": b"**\n!runtime/\n!runtime/**\n", "README.md": readme.encode()}
    receipt = {"schema": 1, "kind": "ultimate-slicer-supervisor-context", "version": version,
        "source_manifest_sha256": pins[0], "source_dockerfile_sha256": pins[1],
        "catalog_sha256": pins[2], "compose_sha256": pins[3], "engine_included": True,
        "engine_executed": False, "image_built": False, "runtime_approved": False,
        "license_review_complete": False, "app_published": False, "app_installed": False,
        "files": [{"path": name, "sha256": dist.sha(raw), "size_bytes": len(raw)}
                  for name, raw in sorted(result.items())]}
    result[RECEIPT] = dist.canonical(receipt)
    return result


def verify(output, *pins, cancelled=None):
    root = dist.safe_path(output)
    require(len(pins) == 4, "four_runtime_pins_required")
    baseline = runtime.verify(root / "runtime", *pins, cancelled=cancelled)
    files = generated(root / "runtime", pins)
    require({p.name for p in root.iterdir()} == set(files) | {"runtime"}, "app_context_members_mismatch")
    for name, expected in files.items():
        path = root / name
        require(dist.read_bounded(path, runtime.LIMIT) == expected, "app_context_bytes_mismatch")
        require(path.stat().st_nlink == 1, "app_context_link_rejected")
        if os.name == "posix":
            require(stat.S_IMODE(path.stat().st_mode) == 0o644, "app_context_mode_mismatch")
    return {"app_context_verified": True, "runtime_context_files": baseline["file_count"],
        "app_metadata_files": len(files), "app_receipt_sha256": dist.sha(files[RECEIPT]),
        "engine_included": True, "engine_executed": False, "image_built": False,
        "runtime_approved": False, "license_review_complete": False, "app_published": False,
        "app_installed": False}


def prepare(input_context, output, *pins, cancelled=None):
    source, output = map(dist.safe_path, (input_context, output))
    require(len(pins) == 4, "four_runtime_pins_required")
    runtime.staging._private_parent(output.parent)
    require(not os.path.lexists(output), "app_output_exists")
    require(source != output and source not in output.parents and output not in source.parents,
            "app_input_output_overlap")
    code = Path(__file__).resolve().parents[1]
    require(output != code and code not in output.parents, "app_output_inside_source")
    runtime.verify(source, *pins, cancelled=cancelled)
    files = generated(source, pins)
    guard = runtime.staging._Guard(cancelled)
    stage = Path(tempfile.mkdtemp(prefix=".supervisor-context-", dir=output.parent))
    owner, complete = stage.stat(), False
    try:
        for path in sorted(source.rglob("*")):
            guard.check(); dist.safe_path(path)
            target = stage / "runtime" / path.relative_to(source)
            if path.is_dir():
                target.mkdir(mode=0o755, parents=True, exist_ok=True)
                continue
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            with dist.regular(path) as inp, target.open("xb") as out:
                while raw := inp.read(dist.CHUNK):
                    guard.check(); out.write(raw)
                out.flush(); os.fsync(out.fileno())
            target.chmod(stat.S_IMODE(path.stat().st_mode))
        for name, data in files.items():
            target = stage / name
            with target.open("xb") as out:
                out.write(data); out.flush(); os.fsync(out.fileno())
            target.chmod(0o644)
        runtime.verify(source, *pins, cancelled=cancelled)
        result = verify(stage, *pins, cancelled=cancelled)
        for directory in sorted((p for p in stage.rglob("*") if p.is_dir()), key=lambda p:len(p.parts), reverse=True):
            runtime.activation._fsync_directory(directory)
        runtime.activation._fsync_directory(stage)
        guard.check(); runtime._publish(stage, output); complete = True
        runtime.activation._fsync_directory(output.parent)
        return result
    finally:
        if not complete:
            dist.safe_path(stage)
            require(os.path.samestat(owner, stage.stat()), "app_output_identity_changed")
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-manifest", "source-dockerfile", "catalog", "compose"):
        parser.add_argument("--expected-" + name + "-sha256", required=True)
    parser.add_argument("--runtime-context", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    pins = (args.expected_source_manifest_sha256, args.expected_source_dockerfile_sha256,
            args.expected_catalog_sha256, args.expected_compose_sha256)
    if not ((args.verify and not args.runtime_context and not args.output)
            or (not args.verify and args.runtime_context and args.output)):
        parser.error("use --verify DIRECTORY or both preparation paths")
    try:
        result = verify(args.verify, *pins) if args.verify else prepare(args.runtime_context, args.output, *pins)
        print(json.dumps(result, sort_keys=True)); return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        print(json.dumps({"ok": False, "error": "app_context_rejected"})); return 2


if __name__ == "__main__":
    raise SystemExit(main())
