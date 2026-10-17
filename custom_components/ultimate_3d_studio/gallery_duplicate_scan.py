"""Bounded, read-only byte-duplicate inspection of the configured model library.

No file is deleted, merged or rewritten. Equal digests are byte equality, not a
claim that two differently encoded meshes are geometrically equivalent. Results
are a checked observation, never authorization for a later deletion.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import threading
import time
from typing import Any

MODEL_SUFFIXES = frozenset({".stl", ".3mf", ".obj"})
CHUNK_BYTES = 1024 * 1024
MAX_ENTRIES = 20_000
MAX_HASH_BYTES = 2 * 1024**3
MAX_DEPTH = 64
MAX_SECONDS = 20.0


class DuplicateScanError(ValueError):
    """A stable error code without absolute paths or source contents."""


def _version(value: os.stat_result) -> tuple:
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _is_link(path: Path, info: os.stat_result) -> bool:
    # Reject symlinks and Windows junction/name-surrogate reparse points; cloud
    # placeholders alone are not directory traversal links.
    return (stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_reparse_tag", 0) & 0x20000000)
            or bool(getattr(path, "is_junction", lambda: False)()))


def _relative_folder(folder: str) -> tuple[str, ...]:
    if not isinstance(folder, str) or len(folder) > 2048:
        raise DuplicateScanError("invalid_folder")
    if not folder:
        return ()
    if ("\\" in folder or ":" in folder or any(ord(c) < 32 for c in folder)
            or any(p in {"", ".", ".."} for p in folder.split("/"))):
        raise DuplicateScanError("invalid_folder")
    value = PurePosixPath(folder)
    if value.is_absolute():
        raise DuplicateScanError("invalid_folder")
    return value.parts


def scan_gallery_duplicates(
    root: Path, folder: str = "", *, cancel: threading.Event | None = None,
    max_entries: int = MAX_ENTRIES, max_hash_bytes: int = MAX_HASH_BYTES,
    timeout_seconds: float = MAX_SECONDS,
) -> dict[str, Any]:
    """Compare models below an explicitly requested folder without mutating it.

    Every result is complete for the declared scope. Budget, read or concurrent
    modification failures return no partial groups. Hardlink aliases are shown
    but do not count as independent copies or potential disk-space recovery.
    """
    if (type(max_entries) is not int or not 1 <= max_entries <= MAX_ENTRIES
            or type(max_hash_bytes) is not int or not 0 <= max_hash_bytes <= MAX_HASH_BYTES
            or isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not 0 < timeout_seconds <= MAX_SECONDS):
        raise DuplicateScanError("invalid_limits")
    parts = _relative_folder(folder)
    deadline = time.monotonic() + timeout_seconds

    def check_budget() -> None:
        if cancel is not None and cancel.is_set():
            raise DuplicateScanError("scan_cancelled")
        if time.monotonic() >= deadline:
            raise DuplicateScanError("scan_time_limit")

    try:
        check_budget()
        # The configured root is a trusted application setting, not request data.
        root = Path(root).resolve(strict=True)
        if not root.is_dir():
            raise DuplicateScanError("folder_not_found")
        current = root
        ancestors: dict[str, tuple] = {"": _version(root.lstat())}
        for part in parts:
            current = current / part
            info = current.lstat()
            if _is_link(current, info) or not stat.S_ISDIR(info.st_mode):
                raise DuplicateScanError("unsafe_folder")
            ancestors[current.relative_to(root).as_posix()] = _version(info)

        def snapshot() -> tuple[dict[str, tuple], dict[str, os.stat_result], int]:
            tree: dict[str, tuple] = {}
            files: dict[str, os.stat_result] = {}
            skipped_links = 0
            stack = [(current, 0)]
            count = 0
            while stack:
                directory, depth = stack.pop()
                check_budget()
                if depth > MAX_DEPTH:
                    raise DuplicateScanError("scan_depth_limit")
                info = directory.lstat()
                if _is_link(directory, info) or not stat.S_ISDIR(info.st_mode):
                    raise DuplicateScanError("library_changed")
                with os.scandir(directory) as entries:
                    for entry in entries:
                        check_budget()
                        count += 1
                        if count > max_entries:
                            raise DuplicateScanError("scan_entry_limit")
                        path = Path(entry.path)
                        # Use path lstat consistently: DirEntry/stat and handle
                        # timestamps do not share ctime semantics on all systems.
                        info = path.lstat()
                        name = path.relative_to(root).as_posix()
                        tree[name] = _version(info)
                        if _is_link(path, info):
                            skipped_links += 1
                        elif stat.S_ISDIR(info.st_mode):
                            stack.append((path, depth + 1))
                        elif stat.S_ISREG(info.st_mode) and path.suffix.lower() in MODEL_SUFFIXES:
                            files[name] = info
            return tree, files, skipped_links

        tree, files, skipped_links = snapshot()
        by_size: dict[int, list[str]] = defaultdict(list)
        for name, info in files.items():
            if info.st_size < 0:
                raise DuplicateScanError("invalid_file_size")
            by_size[info.st_size].append(name)
        candidates = sorted(name for names in by_size.values() if len(names) > 1 for name in names)
        required_bytes = sum(files[name].st_size for name in candidates)
        if required_bytes > max_hash_bytes:
            raise DuplicateScanError("scan_byte_limit")
        groups: dict[tuple[int, str], list[str]] = defaultdict(list)
        hashed_bytes = 0
        for name in candidates:
            check_budget()
            path = root.joinpath(*PurePosixPath(name).parts)
            # Check every ancestor before opening a model; never follow a newly
            # introduced symlink out of the selected library subtree.
            for parent in (path.parent, *path.parent.parents):
                if parent == root:
                    break
                info = parent.lstat()
                if _is_link(parent, info) or not stat.S_ISDIR(info.st_mode):
                    raise DuplicateScanError("library_changed")
            before = path.lstat()
            if _is_link(path, before) or _version(before) != _version(files[name]):
                raise DuplicateScanError("library_changed")
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(path, flags)
            with os.fdopen(fd, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (not stat.S_ISREG(opened.st_mode) or not os.path.samestat(before, opened)
                        or before.st_size != opened.st_size):
                    raise DuplicateScanError("library_changed")
                sha = hashlib.sha256()
                remaining = before.st_size
                while remaining:
                    check_budget()
                    chunk = stream.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        raise DuplicateScanError("library_changed")
                    sha.update(chunk)
                    hashed_bytes += len(chunk)
                    remaining -= len(chunk)
                if stream.read(1) or _version(opened) != _version(os.fstat(stream.fileno())):
                    raise DuplicateScanError("library_changed")
            if _version(before) != _version(path.lstat()):
                raise DuplicateScanError("library_changed")
            groups[(before.st_size, sha.hexdigest())].append(name)

        # Re-enumeration catches renames, new files, removed entries and changes
        # to single-size models which were correctly excluded from hashing.
        if snapshot()[0] != tree:
            raise DuplicateScanError("library_changed")
        for name, expected in ancestors.items():
            if _version((root / name).lstat()) != expected:
                raise DuplicateScanError("library_changed")
        check_budget()
        duplicates = []
        for (size, sha), names in sorted(groups.items()):
            if len(names) < 2:
                continue
            identities = {(files[name].st_dev, files[name].st_ino) for name in names}
            duplicates.append({
                "sha256": sha, "size_bytes": size, "paths": sorted(names, key=lambda n: (n.casefold(), n)),
                "independent_copies": len(identities), "hardlink_aliases": len(names) - len(identities),
                "redundant_content_bytes": max(0, len(identities) - 1) * size,
            })
        return {
            "complete": True, "scope": "byte_identical_models_in_folder", "folder": folder,
            "recursive": True, "read_only": True, "files_examined": len(files),
            "files_hashed": len(candidates), "bytes_hashed": hashed_bytes,
            "skipped_links": skipped_links, "groups": duplicates,
            "duplicate_groups": len(duplicates), "disk_space_savings_verified": False,
            "deletion_authorized": False,
        }
    except FileNotFoundError as exc:
        raise DuplicateScanError("folder_not_found" if 'tree' not in locals() else "library_changed") from exc
    except OSError as exc:
        raise DuplicateScanError("scan_io_error") from exc
