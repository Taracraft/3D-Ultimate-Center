"""One-way, hash-verified gallery copy for the private Home Assistant migration.

Source is read-only. Destination must not exist. Dry-run by default.
This tool is not invoked during HACS installation or application startup.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

MAX_FILES = 40_000
MAX_BYTES = 100 * 1024**3
CHUNK_BYTES = 1024 * 1024


class GalleryCopyError(RuntimeError):
    pass


def _hash_file(path: Path) -> str:
    checksum = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def inspect_source(source: Path, destination: Path) -> list[dict]:
    """Read-only complete preflight, rejecting links, special files and overlap."""
    if not source.is_dir() or source.is_symlink():
        raise GalleryCopyError("gallery source must be a regular directory")
    if destination.exists() or destination.is_symlink():
        raise GalleryCopyError("Studio destination already exists; refusing overwrite")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise GalleryCopyError("Studio destination parent must already exist")
    origin = source.resolve(strict=True)
    target = destination.resolve(strict=False)
    if target == origin or target.is_relative_to(origin) or origin.is_relative_to(target):
        raise GalleryCopyError("source and destination must be disjoint")
    if target == destination.parent.resolve(strict=True):
        raise GalleryCopyError("destination is not an isolated subdirectory")
    # The historical archive may live on a separate mounted volume.
    # Staging is created in destination.parent, making the final rename
    # atomic on the destination filesystem without requiring source affinity.

    inventory = []
    total_size = 0
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if item.is_symlink() or any(part in {"", ".", ".."} for part in relative.parts):
            raise GalleryCopyError("linked or unsafe gallery entry")
        if item.is_dir():
            continue
        info = item.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise GalleryCopyError("special gallery file refused")
        if not item.resolve(strict=True).is_relative_to(origin):
            raise GalleryCopyError("gallery entry escapes its root")
        total_size += info.st_size
        if len(inventory) >= MAX_FILES or total_size > MAX_BYTES:
            raise GalleryCopyError("gallery inventory resource limits reached")
        content_hash = _hash_file(item)
        after = item.stat()
        if after.st_size != info.st_size or after.st_mtime_ns != info.st_mtime_ns:
            raise GalleryCopyError("source changed during inventory")
        inventory.append({
            "relative": relative.as_posix(),
            "bytes": info.st_size,
            "sha256": content_hash,
            "mtime_ns": info.st_mtime_ns,
        })
    return inventory


def copy_gallery(source: Path, destination: Path, *, apply: bool = False) -> dict:
    files = inspect_source(source, destination)
    total = sum(item["bytes"] for item in files)
    folders = [item.relative_to(source) for item in sorted(source.rglob("*")) if item.is_dir()]
    summary = {
        "source_files": len(files),
        "source_directories": len(folders),
        "source_bytes": total,
        "source_read_only": True,
        "destination_preexisting": False,
        "copy_performed": False,
        "integrity_verified": True,
    }
    if not apply:
        return summary

    # Staging belongs to destination parent, never to the existing archive.
    stage: Path | None = None
    try:
        stage = Path(tempfile.mkdtemp(prefix=".studio-gallery-transfer-", dir=destination.parent))
        stage.chmod(0o700)
        for folder in folders:
            origin_folder = source / folder
            if not origin_folder.is_dir() or origin_folder.is_symlink():
                raise GalleryCopyError("original folder changed during transfer")
            (stage / folder).mkdir(parents=True, exist_ok=True)
        for record in files:
            relative = Path(record["relative"])
            source_file = source / relative
            target_file = stage / relative
            target_file.parent.mkdir(parents=True, exist_ok=True)
            if source_file.is_symlink() or not source_file.is_file():
                raise GalleryCopyError("source changed before copy")
            with source_file.open("rb") as reader, target_file.open("xb") as writer:
                shutil.copyfileobj(reader, writer, CHUNK_BYTES)
                writer.flush()
                os.fsync(writer.fileno())
            if target_file.stat().st_size != record["bytes"] or _hash_file(target_file) != record["sha256"]:
                raise GalleryCopyError("destination content checksum mismatch")
            old_info = source_file.stat()
            if old_info.st_size != record["bytes"] or old_info.st_mtime_ns != record["mtime_ns"]:
                raise GalleryCopyError("original gallery changed during copy")
            target_file.chmod(0o640)
            os.utime(target_file, ns=(record["mtime_ns"], record["mtime_ns"]))
        if destination.exists() or destination.is_symlink():
            raise GalleryCopyError("destination appeared during copy; refusing overwrite")
        # The complete staging tree is published only after every file matches.
        stage.chmod(0o750)
        stage.rename(destination)
        stage = None
        summary["copy_performed"] = True
        return summary
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only or explicit gallery transfer")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="copy without changing source")
    options = parser.parse_args()
    try:
        result = copy_gallery(options.source, options.destination, apply=options.apply)
    except (OSError, GalleryCopyError):
        print("Gallery transfer refused; no old gallery content modified")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
