"""Materialize verified manufacturer JSON sources; never execute an engine.

The immutable engine image is not modified. Materializers consume this separate
content-addressed cache, built from the publicly delivered profile source bundle.
"""
from __future__ import annotations
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile

import verify_profile_sources as verifier

def materialize(cache_root, *, source_root=None):
    root = Path(source_root) if source_root is not None else Path(__file__).resolve().parent
    source_tree = source_root is not None
    verifier.verify(root, source_tree=source_tree)
    bundle_path = root / ("Slicer-Server/" if source_tree else "") / verifier.BUNDLE_NAME
    raw = verifier.read_regular(bundle_path.parent, bundle_path.name)
    bundle, _objects = verifier.load_bundle(raw)
    files = {PurePosixPath(row["path"]).relative_to("resources/profiles").as_posix(): row["content"].encode("utf-8") for row in bundle["files"]}
    cache = Path(cache_root).absolute()
    for parent in (cache, *cache.parents):
        if parent.is_symlink():
            raise ValueError("linked_profile_cache")
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = cache / hashlib.sha256(raw).hexdigest()

    def verify_cache():
        if not target.is_dir() or target.is_symlink():
            raise ValueError("invalid_profile_cache")
        present = set()
        for path in target.rglob("*"):
            if path.is_symlink():
                raise ValueError("linked_profile_cache")
            if path.is_dir():
                continue
            name = path.relative_to(target).as_posix()
            if name not in files or not path.is_file() or path.read_bytes() != files[name]:
                raise ValueError("profile_cache_changed")
            present.add(name)
        if present != set(files):
            raise ValueError("profile_cache_incomplete")

    if target.exists() or target.is_symlink():
        verify_cache()
        return target
    temporary = Path(tempfile.mkdtemp(prefix="profile-source-", dir=cache))
    try:
        for name, data in files.items():
            path = temporary / name
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o444)
        try:
            temporary.rename(target)
        except OSError as exc:
            if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                raise
        verify_cache()
        return target
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: materialize_profile_sources.py CACHE_ROOT")
    print(materialize(sys.argv[1]))

if __name__ == "__main__":
    main()
