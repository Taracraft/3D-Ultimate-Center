"""Read-only integrity check for an engine-inclusive image; never start engines."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

BASE = "usr/share/ultimate-slicer-server/runtime"
MAX_MANIFEST = 16 * 1024 * 1024


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_metadata_key")
        result[key] = value
    return result


def document(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_metadata")))


def regular(path):
    for current in (path, *path.parents):
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError("linked_image_payload")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("regular_image_file_required")
    return info


def verify(root=Path("/"), *, check_modes=True, _verified_rows=None):
    root = Path(root)
    if not root.is_absolute() or ".." in root.parts:
        raise ValueError("absolute_image_root_required")
    path = root / BASE / "image-manifest.json"
    if regular(path).st_size > MAX_MANIFEST:
        raise ValueError("image_manifest_limit")
    manifest = document(path.read_bytes())
    if (set(manifest) != {"schema", "kind", "engine_included", "runtime_approved", "license_review_complete",
                         "catalog_sha256", "source_manifest_sha256", "generation_id", "files"}
            or type(manifest["schema"]) is not int or manifest["schema"] != 1
            or manifest.get("kind") != "ultimate-slicer-runtime-image"
            or manifest.get("engine_included") is not True
            or manifest.get("runtime_approved") is not False
            or manifest.get("license_review_complete") is not False
            or any(re.fullmatch(r"[0-9a-f]{64}", str(manifest[k])) is None
                   for k in ("catalog_sha256", "source_manifest_sha256"))
            or re.fullmatch(r"g-[0-9a-f]{64}", str(manifest["generation_id"])) is None):
        raise ValueError("invalid_image_manifest")
    rows, seen = manifest.get("files"), set()
    if not isinstance(rows, list) or not rows or len(rows) > 100000:
        raise ValueError("image_manifest_limit")
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"path", "size_bytes", "sha256", "mode"}
                or type(row["path"]) is not str or type(row["size_bytes"]) is not int
                or row["size_bytes"] < 0 or type(row["mode"]) is not int
                or re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"])) is None):
            raise ValueError("invalid_image_manifest_row")
        name = row["path"]
        relative = PurePosixPath(name)
        if (not relative.parts or relative.is_absolute() or "\\" in name
                or ".." in relative.parts or relative.as_posix() != name or name in seen
                or not name.startswith(("engine/", "opt/ultimate-slicer-server/", BASE + "/"))):
            raise ValueError("invalid_image_manifest_path")
        seen.add(name)
        entrypoints = {"engine/bambu_studio/bin/bambu-studio", "engine/prusaslicer/bin/prusa-slicer",
                       "engine/curaengine/bin/CuraEngine"}
        expected_mode = (0o755 if name in entrypoints else 0o555
                         if name == "opt/ultimate-slicer-server/payload/progress-pipe-reader.py" else 0o644)
        if row["mode"] != expected_mode:
            raise ValueError("image_manifest_mode_rejected")
        target = root / name
        before = regular(target)
        if before.st_size != row["size_bytes"]:
            raise ValueError("image_payload_size_mismatch")
        digest = hashlib.sha256()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        with os.fdopen(os.open(target, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not os.path.samestat(before, opened):
                raise ValueError("image_payload_changed")
            while raw := stream.read(65536):
                digest.update(raw)
            after = os.fstat(stream.fileno())
        if (before.st_size != after.st_size or not os.path.samestat(before, regular(target))
                or digest.hexdigest() != row["sha256"]):
            raise ValueError("image_payload_mismatch")
        if check_modes and os.name == "posix" and stat.S_IMODE(after.st_mode) != row["mode"]:
            raise ValueError("image_payload_mode_mismatch")
    for engine, entry in {"bambu_studio": "bambu-studio", "prusaslicer": "prusa-slicer",
                          "curaengine": "CuraEngine"}.items():
        if "engine/" + engine + "/bin/" + entry not in seen:
            raise ValueError("complete_engine_image_required")
    catalog_path = BASE + "/engine-distribution/CATALOG.json"
    source_path = "opt/ultimate-slicer-server/context-manifest.json"
    required = {catalog_path, source_path, "engine/GENERATION.json",
                BASE + "/engine-distribution/DISTRIBUTION.json", BASE + "/runtime_image_check.py"}
    if not required <= seen:
        raise ValueError("image_metadata_missing")
    for name, key in ((catalog_path, "catalog_sha256"), (source_path, "source_manifest_sha256")):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != manifest[key]:
            raise ValueError("image_metadata_digest_mismatch")
    source = document((root / source_path).read_bytes())
    catalog = document((root / catalog_path).read_bytes())
    generation = document((root / "engine/GENERATION.json").read_bytes())
    if generation.get("generation_id") != manifest["generation_id"]:
        raise ValueError("image_generation_mismatch")
    expected_source = {"opt/ultimate-slicer-server/" + r["path"] for r in source["files"]} | {source_path}
    expected_engine = {"engine/" + release["engine"] + "/" + f["path"]
                       for release in catalog["releases"] for a in release["artifacts"] for f in a["files"]}
    if (set(r["engine"] for r in catalog["releases"]) != {"bambu_studio", "prusaslicer", "curaengine"}
            or {n for n in seen if n.startswith("opt/")} != expected_source
            or {n for n in seen if n.startswith("engine/")} != expected_engine | {"engine/GENERATION.json"}):
        raise ValueError("image_payload_closure_mismatch")
    declared = {r["path"]: r for r in rows}
    bindings = [("opt/ultimate-slicer-server/" + r["path"], r) for r in source["files"]]
    bindings.extend(("engine/" + release["engine"] + "/" + f["path"], f)
                    for release in catalog["releases"] for a in release["artifacts"] for f in a["files"])
    for name, expected in bindings:
        if any(declared[name][key] != expected[key] for key in ("sha256", "size_bytes")):
            raise ValueError("image_companion_binding_mismatch")
    if _verified_rows is not None:
        _verified_rows.extend(dict(row) for row in rows)
    return {"image_integrity": "verified", "verified_files": len(rows),
            "engine_included": True, "engine_executed": False,
            "runtime_approved": False, "license_review_complete": False,
            "worker_started": False, "installation_performed": False}


def normalize_modes(root=Path("/")):
    """Explicit image-build helper: validate all bytes and roles before chmod."""
    root = Path(root)
    rows = []
    verify(root, check_modes=False, _verified_rows=rows)
    if not hasattr(os, "fchmod"):
        raise ValueError("image_mode_normalization_requires_posix")
    for row in rows:
        target = root / row["path"]
        before = regular(target)
        fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        try:
            if not os.path.samestat(before, os.fstat(fd)):
                raise ValueError("image_payload_changed")
            os.fchmod(fd, row["mode"])
        finally:
            os.close(fd)
    return verify(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check",), nargs="?", default="check")
    parser.parse_args(argv)
    try:
        result = verify()
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps({"image_integrity": "failed", "runtime_approved": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
