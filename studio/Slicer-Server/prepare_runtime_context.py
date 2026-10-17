"""Bind a verified source context and offline distribution into a new image context.

No archive extraction, network access, engine execution, build or activation.
All expected digests are external inputs; no approval flags are accepted.
"""
from __future__ import annotations

import argparse
import copy
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

import container_check
import package_activation as activation
import package_staging as staging
import prepare_engine_distribution as dist
import runtime_image_check as image_check

LIMIT = 16 * 1024 * 1024
RECEIPT = "runtime-context.json"
IMAGE_BASE = image_check.BASE
IGNORE = ("**\n!Dockerfile\n!source/\n!source/**\n!engine/\n!engine/**\n"
          "!engine-distribution/\n!engine-distribution/**\n!runtime_image_check.py\n!image-manifest.json\n").encode()


class RuntimeContextError(ValueError):
    """Stable diagnostic codes without input paths or private data."""


def require(value, code):
    if not value:
        raise RuntimeContextError(code)


def pinned_read(path, expected):
    raw = dist.read_bounded(path, LIMIT)
    require(dist.sha(raw) == dist.pinned(expected), "input_digest_mismatch")
    return raw


def source_plan(root, manifest_sha256, dockerfile_sha256):
    root = dist.safe_path(root)
    raw = pinned_read(root / "context-manifest.json", manifest_sha256)
    manifest = image_check.document(raw)
    container_check.verify(root)
    dockerfile = pinned_read(root / "Dockerfile", dockerfile_sha256)
    names = {r["path"] for r in manifest["files"]} | {"context-manifest.json", "Dockerfile", ".dockerignore"}
    result = {}
    for name in names:
        data = dist.read_bounded(root / name, LIMIT)
        result[name] = (len(data), dist.sha(data), 0o644)
    copied = set()
    for line in dockerfile.decode("utf-8-sig").splitlines():
        if line.startswith("COPY --chown=65532:65532 "):
            for name in line.split()[2:-1]:
                selected = {n for n in names if n.startswith(name)} if name.endswith("/") else {name}
                require(bool(selected) and selected <= names, "dockerfile_source_missing")
                copied.update(selected)
    require(copied == names - {"Dockerfile", ".dockerignore"}, "dockerfile_payload_mismatch")
    # The inherited checker covers every payload hash. Recheck the manifest and
    # Dockerfile after its reads to bind the two separately pinned inputs.
    require(pinned_read(root / "context-manifest.json", manifest_sha256) == raw
            and pinned_read(root / "Dockerfile", dockerfile_sha256) == dockerfile,
            "source_changed")
    return result, dockerfile


def compose_bytes(raw):
    original = image_check.document(raw)
    value = copy.deepcopy(original)
    services = value.get("services", {})
    expected = {"api": {"/var/lib/ultimate-slicer", "/engine", "/run/secrets/api-token", "/run/tls", "/var/lib/ultimate-slicer-profiles"},
                "worker": {"/var/lib/ultimate-slicer", "/engine", "/var/lib/ultimate-slicer-profiles"},
                "data-init": {"/var/lib/ultimate-slicer"},
                "profile-init": {"/var/lib/ultimate-slicer-profiles"},
                "maintenance-clear": {"/var/lib/ultimate-slicer"}}
    require(set(services) == set(expected), "unsupported_compose_services")
    for name, service in services.items():
        volumes = service.get("volumes")
        require(isinstance(volumes, list) and len(volumes) == len(expected[name])
                and all(isinstance(v, dict) for v in volumes)
                and {v.get("target") for v in volumes} == expected[name], "unsupported_compose_mounts")
        require(service.get("read_only") is True and service.get("user") == "65532:65532"
                and service.get("cap_drop") == ["ALL"]
                and service.get("security_opt") == ["no-new-privileges:true"]
                and not any(k in service for k in ("privileged", "devices", "cap_add", "volumes_from")),
                "compose_isolation_changed")
        for mount in volumes:
            require(mount.get("type") == "bind" and mount.get("bind") == {"create_host_path": False},
                    "unsupported_compose_mounts")
        if name in {"api", "worker"}:
            engine = next(v for v in volumes if v["target"] == "/engine")
            require(engine.get("read_only") is True, "engine_mount_writable")
            service["volumes"] = [v for v in volumes if v["target"] != "/engine"]
    require(services["worker"].get("network_mode") == "none"
            and services["worker"].get("pid") == "service:api", "compose_worker_isolation_changed")
    require(services["maintenance-clear"].get("profiles") == ["maintenance"],
            "maintenance_must_be_explicit")
    return dist.canonical(value)


def dockerfile_bytes(raw):
    text = raw.decode("utf-8-sig")
    lines = text.splitlines(keepends=True)
    copies = 0
    for index, line in enumerate(lines):
        if line.startswith("COPY --chown=65532:65532 "):
            parts = line.strip().split()
            require(len(parts) >= 4 and parts[-1].startswith("./"), "unsupported_dockerfile_copy")
            lines[index] = " ".join(parts[:2] + ["source/" + p for p in parts[2:-1]] + parts[-1:]) + "\n"
            copies += 1
    require(copies == 3 and text.count("USER 65532:65532") == 1
            and text.count('ENTRYPOINT ["python3", "/opt/ultimate-slicer-server/container_check.py"]') == 1,
            "unsupported_source_dockerfile")
    text = "".join(lines)
    extra = ("COPY --chown=65532:65532 engine/ /engine/\n"
             "COPY --chown=65532:65532 engine-distribution/ /" + IMAGE_BASE + "/engine-distribution/\n"
             "COPY --chown=65532:65532 runtime_image_check.py image-manifest.json /" + IMAGE_BASE + "/\n"
             # Docker contexts made on Windows do not preserve executable bits.
             # Normalize only the exact generated file list, then read-check it.
             "RUN python3 -c 'import sys; sys.path.insert(0, \"/" + IMAGE_BASE + "\"); "
             "import runtime_image_check; runtime_image_check.normalize_modes()'\n")
    text = text.replace("USER 65532:65532", extra + "USER 65532:65532")
    text = text.replace('ENTRYPOINT ["python3", "/opt/ultimate-slicer-server/container_check.py"]',
                        'ENTRYPOINT ["python3", "/' + IMAGE_BASE + '/runtime_image_check.py"]')
    return text.encode()


def plans(source, distribution, compose, manifest_pin, dockerfile_pin, catalog_pin, compose_pin):
    source_rows, original_dockerfile = source_plan(source, manifest_pin, dockerfile_pin)
    raw_catalog = pinned_read(distribution / dist.CATALOG, catalog_pin)
    releases = dist.load_inputs(raw_catalog, catalog_pin)
    metadata, engine_rows = dist.members(releases, raw_catalog)
    for name, expected in metadata.items():
        require(dist.read_bounded(distribution / name, LIMIT) == expected, "distribution_metadata_mismatch")
    raw_compose = pinned_read(compose, compose_pin)
    generated = {"Dockerfile": dockerfile_bytes(original_dockerfile), ".dockerignore": IGNORE,
                 "compose.source.json": raw_compose, "compose.runtime.yaml": compose_bytes(raw_compose),
                 "runtime_image_check.py": dist.read_bounded(Path(__file__).with_name("runtime_image_check.py"), LIMIT)}
    rows, sources = {}, {}
    for name, spec in source_rows.items():
        rows["source/" + name] = spec
        sources["source/" + name] = source / name
    for name, spec in engine_rows.items():
        if name.startswith("engine/"):
            rows[name], sources[name] = spec, distribution / name
        else:
            generated["engine-distribution/" + name] = metadata[name]
    image_rows = []
    for name, (size, digest, mode) in rows.items():
        if name.startswith("source/"):
            if name.removeprefix("source/") in {"Dockerfile", ".dockerignore"}:
                continue
            target = "opt/ultimate-slicer-server/" + name.removeprefix("source/")
            # The existing Dockerfile intentionally makes this helper executable.
            if name == "source/payload/progress-pipe-reader.py":
                mode = 0o555
        else:
            target = name
        image_rows.append({"path": target, "size_bytes": size, "sha256": digest, "mode": mode})
    for name, data in generated.items():
        if name.startswith("engine-distribution/") or name == "runtime_image_check.py":
            image_rows.append({"path": IMAGE_BASE + "/" + name, "size_bytes": len(data),
                               "sha256": dist.sha(data), "mode": 0o644})
    generated["image-manifest.json"] = dist.canonical({"schema": 1, "kind": "ultimate-slicer-runtime-image",
        "engine_included": True, "runtime_approved": False, "license_review_complete": False,
        "catalog_sha256": catalog_pin, "source_manifest_sha256": manifest_pin,
        "generation_id": activation._generation_document(releases)["generation_id"],
        "files": sorted(image_rows, key=lambda r: r["path"])})
    for name, data in generated.items():
        rows[name] = (len(data), dist.sha(data), 0o644)
    receipt = {"schema": 1, "kind": "ultimate-slicer-runtime-context", "engine_included": True,
        "engine_executed": False, "runtime_approved": False, "license_review_complete": False,
        "container_deploy_ready": False, "image_built": False,
        "source_manifest_sha256": manifest_pin, "source_dockerfile_sha256": dockerfile_pin,
        "catalog_sha256": catalog_pin, "compose_sha256": compose_pin,
        "files": [{"path": n, "size_bytes": s, "sha256": h, "mode": m}
                  for n, (s, h, m) in sorted(rows.items())]}
    return rows, sources, generated, receipt, releases


def exact_tree(root, rows):
    expected = set(rows) | {RECEIPT}
    directories = set()
    for name in expected:
        parent = Path(name).parent
        while str(parent) != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    files, actual_dirs = set(), set()
    for path in root.rglob("*"):
        dist.safe_path(path)
        name = path.relative_to(root).as_posix()
        if path.is_dir():
            actual_dirs.add(name)
        elif path.is_file():
            require(path.stat().st_nlink == 1, "linked_context_file")
            files.add(name)
        else:
            raise RuntimeContextError("unsupported_context_member")
    require(files == expected and actual_dirs == directories, "context_members_mismatch")


def verify(output, manifest_pin, dockerfile_pin, catalog_pin, compose_pin, *, cancelled=None):
    root = dist.safe_path(output)
    staging._private_parent(root)
    # Metadata is reconstructed from independently pinned inputs, never trusted
    # merely because a self-declared output manifest was changed with its files.
    rows, _, _, receipt, releases = _output_plan(root, manifest_pin, dockerfile_pin, catalog_pin, compose_pin)
    exact_tree(root, rows)
    guard = staging._Guard(cancelled)
    for name, (size, digest, mode) in rows.items():
        dist.check_file(root / name, size, digest, guard)
        if os.name == "posix":
            require(stat.S_IMODE((root / name).stat().st_mode) == mode, "context_mode_mismatch")
    for engine, release in releases.items():
        activation._validate_tree(root / "engine" / engine, release)
    require(dist.read_bounded(root / RECEIPT, LIMIT) == dist.canonical(receipt), "context_receipt_mismatch")
    return {"runtime_context_verified": True, "file_count": len(rows) + 1,
            "manifest_sha256": dist.sha(dist.canonical(receipt)), "engine_included": True,
            "engine_executed": False, "image_built": False, "runtime_approved": False,
            "license_review_complete": False, "container_deploy_ready": False}


def _output_plan(root, manifest_pin, dockerfile_pin, catalog_pin, compose_pin):
    # The image context deliberately excludes the distribution archive. Reuse
    # the same catalog-derived metadata/file contract, without another unpacker.
    return plans(root / "source", _OutputDistribution(root), root / "compose.source.json",
                 manifest_pin, dockerfile_pin, catalog_pin, compose_pin)


class _OutputDistribution:
    def __init__(self, root):
        self.root = root
    def __truediv__(self, name):
        return self.root / name if name.startswith("engine/") else self.root / "engine-distribution" / name


def _publish(stage, output):
    """Atomically publish without replacing even an empty competing directory."""
    if os.name == "nt":
        os.rename(stage, output)  # Windows rename never replaces an existing path.
    elif sys.platform.startswith("linux"):
        rename = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
        require(rename is not None, "exclusive_atomic_rename_unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(stage), -100, os.fsencode(output), 1):  # AT_FDCWD, RENAME_NOREPLACE
            code = ctypes.get_errno()
            raise OSError(code, errno.errorcode.get(code, "exclusive_rename_failed"))
    else:
        raise RuntimeContextError("exclusive_atomic_rename_unavailable")


def prepare(source, distribution, compose, output, manifest_pin, dockerfile_pin, catalog_pin, compose_pin,
            *, cancelled=None):
    source, distribution, compose, output = map(dist.safe_path, (source, distribution, compose, output))
    staging._private_parent(output.parent)
    require(not os.path.lexists(output), "output_exists")
    code = Path(__file__).resolve().parents[1]
    for path in (source, distribution, compose, code):
        require(output != path and path not in output.parents and output not in path.parents,
                "input_output_overlap")
    dist.verify(distribution, catalog_pin, cancelled=cancelled)
    rows, sources, generated, receipt, _ = plans(source, distribution, compose,
                                                manifest_pin, dockerfile_pin, catalog_pin, compose_pin)
    guard = staging._Guard(cancelled)
    guard.check()
    stage = Path(tempfile.mkdtemp(prefix=".runtime-context-", dir=output.parent))
    owner, complete = stage.stat(), False
    try:
        for name, (size, digest, mode) in sorted(rows.items()):
            guard.check()
            target = stage / name
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            with target.open("xb") as stream:
                if name in generated:
                    stream.write(generated[name])
                else:
                    sink = hashlib.sha256()
                    with dist.regular(sources[name]) as input_stream:
                        require(os.fstat(input_stream.fileno()).st_size == size, "input_size_changed")
                        while raw := input_stream.read(dist.CHUNK):
                            guard.check()
                            sink.update(raw)
                            stream.write(raw)
                    require(sink.hexdigest() == digest, "input_changed")
                stream.flush()
                os.fsync(stream.fileno())
            target.chmod(mode)
        # Recheck every original input after copying before writing a completion receipt.
        dist.verify(distribution, catalog_pin, cancelled=cancelled)
        source_plan(source, manifest_pin, dockerfile_pin)
        pinned_read(compose, compose_pin)
        with (stage / RECEIPT).open("xb") as stream:
            stream.write(dist.canonical(receipt))
            stream.flush()
            os.fsync(stream.fileno())
        (stage / RECEIPT).chmod(0o644)
        result = verify(stage, manifest_pin, dockerfile_pin, catalog_pin, compose_pin, cancelled=cancelled)
        for directory in sorted((p for p in stage.rglob("*") if p.is_dir()),
                                key=lambda p: len(p.parts), reverse=True):
            activation._fsync_directory(directory)
        activation._fsync_directory(stage)
        guard.check()
        _publish(stage, output)
        complete = True
        activation._fsync_directory(output.parent)
        return result
    finally:
        if not complete:
            dist.safe_path(stage)
            require(os.path.samestat(owner, stage.stat()), "output_identity_changed")
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-manifest", "source-dockerfile", "catalog", "compose"):
        parser.add_argument("--expected-" + name + "-sha256", required=True)
    parser.add_argument("--source-context", type=Path)
    parser.add_argument("--engine-distribution", type=Path)
    parser.add_argument("--compose", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    pins = (args.expected_source_manifest_sha256, args.expected_source_dockerfile_sha256,
            args.expected_catalog_sha256, args.expected_compose_sha256)
    inputs = (args.source_context, args.engine_distribution, args.compose, args.output)
    if not ((args.verify and not any(inputs)) or (not args.verify and all(inputs))):
        parser.error("use --verify DIRECTORY or all four preparation paths")
    try:
        result = verify(args.verify, *pins) if args.verify else prepare(*inputs, *pins)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        print(json.dumps({"ok": False, "error": "runtime_context_rejected"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
