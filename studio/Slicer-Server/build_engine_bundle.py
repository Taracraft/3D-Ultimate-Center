"""Deterministic, inventory-bound engine archive builder; never executes payloads.

Builds concrete binary/resource archives from already reviewed local files.
Packaging is not a license, runtime or deployment approval. Root paths remain
local input only; neither those paths nor user configuration enter the bundle.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile

ENTRIES = {"bambu_studio": "bin/bambu-studio", "prusaslicer": "bin/prusa-slicer", "curaengine": "bin/CuraEngine"}
ROLES = {"engine", "runtime", "resources", "profiles", "license", "source"}
MAX_FILES = 100000
MAX_FILE_BYTES = 512 * 1024**2
MAX_TOTAL_BYTES = 8 * 1024**3
MANIFEST_NAME = "bundle-manifest.json"
CHUNK = 65536

class BundleError(ValueError):
    """Stable code without supplied paths, URLs or file content."""


def require(value, code):
    if not value:
        raise BundleError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def relative(value):
    require(type(value) is str and 0 < len(value) <= 512, "invalid_path")
    require(not value.startswith("/") and not any(c in value for c in "\\:\x00")
            and not any(ord(c) < 32 for c in value)
            and all(p not in ("", ".", "..") for p in value.split("/")), "invalid_path")
    require(PurePosixPath(value).as_posix() == value, "invalid_path")
    return value


def safe_local(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        require(not part.is_symlink() and not getattr(part, "is_junction", lambda: False)(), "linked_local_path")
    return path


def validate(inventory):
    require(type(inventory) is dict and set(inventory) == {"schema", "engine", "version", "upstream_archives", "files"}, "invalid_inventory")
    require(type(inventory["schema"]) is int and inventory["schema"] == 1, "invalid_schema")
    engine = inventory["engine"]
    require(type(engine) is str and engine in ENTRIES, "invalid_engine")
    version = inventory["version"]
    require(type(version) is str and re.fullmatch(r"[0-9][A-Za-z0-9.+_:-]{0,119}", version), "unfixed_version")
    archives = inventory["upstream_archives"]
    require(type(archives) is list and 1 <= len(archives) <= 64, "missing_upstream_archives")
    ids = set()
    for item in archives:
        require(type(item) is dict and set(item) == {"id", "sha256", "bytes"}, "invalid_upstream_archive")
        require(type(item["id"]) is str and re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", item["id"]), "invalid_upstream_archive")
        require(item["id"] not in ids, "duplicate_upstream_archive")
        ids.add(item["id"])
        require(type(item["sha256"]) is str and re.fullmatch(r"[a-f0-9]{64}", item["sha256"]), "invalid_digest")
        require(type(item["bytes"]) is int and 0 < item["bytes"] <= MAX_TOTAL_BYTES, "invalid_size")
    files = inventory["files"]
    require(type(files) is list and 1 <= len(files) <= MAX_FILES, "invalid_file_count")
    names = {}; count = 0; total = 0
    for item in files:
        require(type(item) is dict and set(item) == {"root", "source", "path", "sha256", "bytes", "role", "executable"}, "invalid_file")
        require(type(item["root"]) is str and re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", item["root"]), "invalid_root_id")
        relative(item["source"]); name = relative(item["path"])
        require(name != MANIFEST_NAME, "reserved_bundle_path")
        require(type(item["sha256"]) is str and re.fullmatch(r"[a-f0-9]{64}", item["sha256"]), "invalid_digest")
        require(type(item["bytes"]) is int and 0 <= item["bytes"] <= MAX_FILE_BYTES, "invalid_size")
        require(type(item["role"]) is str and item["role"] in ROLES and type(item["executable"]) is bool, "invalid_role")
        require(not item["executable"] or item["role"] == "engine", "unexpected_executable")
        parts = name.split("/")
        for n in range(1, len(parts) + 1):
            part = "/".join(parts[:n]); kind = "file" if n == len(parts) else "directory"
            key = part.casefold()
            require(key not in names or (names[key] == (part, "directory") and kind == "directory"), "conflicting_paths")
            names[key] = (part, kind)
        if item["role"] == "engine":
            count += 1
            require(name == ENTRIES[engine] and item["executable"] and item["bytes"] > 0, "invalid_entrypoint")
        total += item["bytes"]
    require(count == 1 and total <= MAX_TOTAL_BYTES, "invalid_payload")
    require(any(f["role"] == "license" and f["bytes"] > 0 for f in files), "missing_license")
    require(any(f["role"] == "profiles" and f["bytes"] > 0 for f in files), "missing_profiles")
    require(any(f["role"] == "resources" and f["bytes"] > 0 for f in files), "missing_resources")
    return inventory


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode)


def stream_source(root, item):
    path = safe_local(safe_local(root) / item["source"])
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == item["bytes"], "invalid_source_file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0))
    stream = os.fdopen(fd, "rb")
    opened = os.fstat(fd)
    if not os.path.samestat(before, opened) or opened.st_size != before.st_size:
        stream.close()
        raise BundleError("source_changed")
    return path, before, opened, stream


class HashReader:
    def __init__(self, stream):
        self.stream = stream; self.hash = hashlib.sha256(); self.total = 0
    def read(self, n):
        require(type(n) is int and n >= 0, "unbounded_read")
        data = self.stream.read(min(n, CHUNK))
        self.hash.update(data); self.total += len(data)
        return data


def manifest(inventory):
    return {"schema": 1, "engine": inventory["engine"], "version": inventory["version"],
            "system": "linux", "architecture": "amd64",
            "upstream_archives": inventory["upstream_archives"],
            "files": [{k: f[k] for k in ("path", "bytes", "sha256", "role", "executable")}
                      for f in sorted(inventory["files"], key=lambda f: f["path"])],
            "engine_executed": False, "runtime_approved": False,
            "license_review_complete": False, "release_approved": False}


def verify(archive_path, expected):
    rows = {f["path"]: f for f in expected["files"]}
    wanted_manifest = canonical(expected); found = set()
    with tarfile.open(archive_path, mode="r:gz") as tar:
        for item in tar:
            name = relative(item.name)
            require(name not in found and item.isfile() and item.uid == item.gid == item.mtime == 0
                    and not item.uname and not item.gname, "invalid_archive_member")
            found.add(name)
            if name == MANIFEST_NAME:
                require(item.size == len(wanted_manifest) and item.mode == 0o644, "invalid_manifest")
                require(tar.extractfile(item).read() == wanted_manifest, "manifest_mismatch")
                continue
            require(name in rows, "unexpected_archive_member")
            f = rows[name]
            require(item.size == f["bytes"] and item.mode == (0o755 if f["executable"] else 0o644), "archive_metadata_mismatch")
            h = hashlib.sha256(); n = 0
            with tar.extractfile(item) as stream:
                while chunk := stream.read(CHUNK):
                    n += len(chunk); h.update(chunk)
            require(n == f["bytes"] and h.hexdigest() == f["sha256"], "archive_digest_mismatch")
    require(found == set(rows) | {MANIFEST_NAME}, "archive_members_missing")
    return True


def build(inventory, roots, output):
    # Detach caller-owned mutable records before reading any files.
    inventory = validate(json.loads(canonical(inventory)))
    require(type(roots) is dict and set(roots) == {f["root"] for f in inventory["files"]}, "root_mapping_mismatch")
    roots = {name: safe_local(path) for name, path in roots.items()}
    require(all(path.is_dir() for path in roots.values()), "source_root_missing")
    output = safe_local(output)
    require(not output.exists(), "output_exists")
    require(not any(output == root or root in output.parents for root in roots.values()), "output_inside_source")
    # All source names are checked before creating output; payload bytes are
    # hashed while writing and again through the completed archive verifier.
    for f in inventory["files"]:
        path, before, opened, stream = stream_source(roots[f["root"]], f)
        stream.close()
    output.mkdir(parents=True)
    archive_path = output / (inventory["engine"] + ".tar.gz")
    pending = output / ".archive-incomplete"
    m = manifest(inventory); mraw = canonical(m)
    try:
        with pending.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target, compresslevel=6, mtime=0) as gz:
                with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
                    for f in sorted(inventory["files"], key=lambda f: f["path"]):
                        path, before, opened, stream = stream_source(roots[f["root"]], f)
                        with stream:
                            reader = HashReader(stream)
                            info = tarfile.TarInfo(f["path"]); info.size = f["bytes"]
                            info.mode = 0o755 if f["executable"] else 0o644
                            tar.addfile(info, reader)
                            require(reader.total == f["bytes"] and reader.hash.hexdigest() == f["sha256"]
                                    and not stream.read(1), "source_digest_mismatch")
                            require(identity(opened) == identity(os.fstat(stream.fileno()))
                                    and identity(before) == identity(path.stat()), "source_changed")
                    info = tarfile.TarInfo(MANIFEST_NAME); info.size = len(mraw); info.mode = 0o644
                    tar.addfile(info, io.BytesIO(mraw))
            target.flush(); os.fsync(target.fileno())
        verify(pending, m)
        pending.rename(archive_path)
        (output / MANIFEST_NAME).write_bytes(mraw)
        h = hashlib.sha256()
        with archive_path.open("rb") as stream:
            while chunk := stream.read(CHUNK): h.update(chunk)
        result = {"schema": 1, "engine": inventory["engine"], "version": inventory["version"],
                  "payload_files": len(inventory["files"]), "payload_bytes": sum(f["bytes"] for f in inventory["files"]),
                  "archive_bytes": archive_path.stat().st_size, "archive_sha256": h.hexdigest(),
                  "manifest_sha256": digest(mraw), "archive_verified": True,
                  "engine_executed": False, "release_approved": False}
        (output / "BUILD_RESULT.json").write_bytes(canonical(result))
        (output / "SHA256SUMS").write_text(h.hexdigest() + "  " + archive_path.name + "\n" + digest(mraw) + "  " + MANIFEST_NAME + "\n", encoding="ascii")
        return result
    except Exception:
        # Preserve only this newly claimed output for diagnosis. An incomplete
        # archive has no final filename or successful BUILD_RESULT receipt.
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", required=True, type=Path)
    p.add_argument("--roots", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        result = build(json.loads(a.inventory.read_bytes()), json.loads(a.roots.read_bytes()), a.output)
        print(json.dumps(result, sort_keys=True)); return 0
    except Exception:
        print(json.dumps({"ok": False, "error": "engine_bundle_build_failed"})); return 2

if __name__ == "__main__":
    raise SystemExit(main())
