"""Read-only source preflight. Never import or execute the packaged worker."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

def verify(root):
    root = Path(root)
    manifest_path = root / "context-manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("linked_manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or manifest.get("container_stage") != "source-preflight":
        raise ValueError("unsupported_manifest")
    if manifest.get("container_deploy_ready") is not False or manifest.get("engine_included") is not False:
        raise ValueError("preview_release_flags_changed")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("empty_manifest")
    seen = set()
    for row in rows:
        name = row["path"]
        relative = PurePosixPath(name)
        if not relative.parts or relative.is_absolute() or "\\" in name or ".." in relative.parts or name in seen:
            raise ValueError("unsafe_or_duplicate_manifest_path")
        seen.add(name)
        target = root
        for part in relative.parts:
            target = target / part
            if target.is_symlink() or getattr(target, "is_junction", lambda: False)():
                raise ValueError("linked_payload")
        if not target.is_file():
            raise ValueError("missing_payload:" + name)
        data = target.read_bytes()
        if len(data) != row["size_bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("payload_mismatch:" + name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()}
    allowed = seen | {"context-manifest.json", "Dockerfile", ".dockerignore"}
    if actual - allowed:
        raise ValueError("unexpected_context_file")
    return {"source_integrity": "verified", "verified_files": len(seen),
            "version": manifest["version"], "api_protocol": manifest["api_protocol"],
            "container_deploy_ready": False, "engine_included": False,
            "installation_performed": False, "worker_started": False}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check",), nargs="?", default="check")
    parser.parse_args(argv)
    try:
        result = verify(Path(__file__).resolve().parent)
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps({"source_integrity": "failed", "container_deploy_ready": False}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
