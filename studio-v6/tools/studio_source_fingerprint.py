"""Read-only source inventory with SHA-256 and Git's byte-exact blob identity.

This module neither publishes files nor executes inventoried source. It excludes
runtime data and recovery copies. A manifest describes its explicit source scope,
not permission to publish private documentation or a complete live deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOTS = ("api", "core", "frontend", "frontend-tests", "tests", "tools", "docs", "deploy")
ROOT_FILES = ("AGENTS.md", "README.md", "LIVE_WORKLOG.md", "CHANGELOG.md", "CHANGELOG-DE.md",
              "package.json", "package-lock.json", "tsconfig.json", "pyproject.toml",
              "build_frontend.mjs", "build_v6_core.mjs", "run_frontend_logic_tests.mjs",
              "run_frontend_tests.mjs", "run_python_tests.py", "connector_v6_gate.py")
EXCLUDED_PARTS = frozenset({".git", "node_modules", "__pycache__", "backups", "backup",
                           "data", "run", "runtime", "engines", "uploads", "output", "logs"})
EXCLUDED_NAMES = frozenset({"config.json", "options.json", "secrets.yaml", "token", "auth"})
RECOVERY = re.compile(r"(?:\.(?:bak|backup|before)(?:[._-]|$)|~$)", re.I)
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_FILES = 5000


class SourceInventoryError(ValueError):
    """An explicit incomplete/unsafe inventory, never an empty success."""


def _version(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def fingerprint(path: Path) -> dict:
    """Compare lstat with lstat and fstat with fstat across Windows and Linux."""
    before = path.lstat()
    if _link(path) or not stat.S_ISREG(before.st_mode):
        raise SourceInventoryError("source_is_not_regular")
    if not 0 <= before.st_size <= MAX_FILE_BYTES:
        raise SourceInventoryError("source_size_limit")
    sha256 = hashlib.sha256()
    git_blob = hashlib.sha1(f"blob {before.st_size}\0".encode("ascii"), usedforsecurity=False)
    count = 0
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(before, opened):
            raise SourceInventoryError("source_changed")
        while chunk := stream.read(1024 * 1024):
            count += len(chunk)
            if count > before.st_size:
                raise SourceInventoryError("source_changed")
            sha256.update(chunk)
            git_blob.update(chunk)
        if _version(opened) != _version(os.fstat(stream.fileno())):
            raise SourceInventoryError("source_changed")
    if count != before.st_size or _version(before) != _version(path.lstat()):
        raise SourceInventoryError("source_changed")
    return {"size_bytes": count, "sha256": sha256.hexdigest(), "git_blob_sha": git_blob.hexdigest()}


def source_paths(root: Path) -> list[Path]:
    if not root.is_dir() or _link(root):
        raise SourceInventoryError("invalid_source_root")
    result = []
    for name in ROOT_FILES:
        path = root / name
        if path.exists() or path.is_symlink():
            if _link(path):
                raise SourceInventoryError("linked_source")
            result.append(path)
    for name in ROOTS:
        base = root / name
        if not base.exists():
            continue
        if _link(base) or not base.is_dir():
            raise SourceInventoryError("linked_source")
        for directory, dirs, files in os.walk(base, followlinks=False):
            current = Path(directory)
            retained = []
            for child in dirs:
                if child.startswith(".") or child.casefold() in EXCLUDED_PARTS or RECOVERY.search(child):
                    continue
                if _link(current / child):
                    raise SourceInventoryError("linked_source")
                retained.append(child)
            dirs[:] = retained
            for child in files:
                if (child.startswith(".") or child.casefold() in EXCLUDED_NAMES
                        or RECOVERY.search(child) or Path(child).suffix.lower() in {".pyc", ".pyo", ".log", ".tmp", ".zip", ".b64", ".woff", ".woff2", ".ttf", ".otf"}):
                    continue
                path = current / child
                if _link(path):
                    raise SourceInventoryError("linked_source")
                result.append(path)
                if len(result) > MAX_FILES:
                    raise SourceInventoryError("source_count_limit")
    return sorted(result, key=lambda p: p.relative_to(root).as_posix())


def source_inventory(root: Path) -> dict:
    root = Path(root).absolute()
    paths = source_paths(root)
    if not paths:
        raise SourceInventoryError("empty_source_inventory")
    records = [{"path": p.relative_to(root).as_posix(), **fingerprint(p)} for p in paths]
    if paths != source_paths(root):
        raise SourceInventoryError("source_set_changed")
    return {"format": 1, "complete_for_declared_scope": True, "published": False,
            "scope_roots": list(ROOTS), "file_count": len(records), "files": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()
    try:
        result = source_inventory(args.source_root)
    except (SourceInventoryError, OSError) as error:
        print(json.dumps({"complete_for_declared_scope": False,
                          "error": str(error) if isinstance(error, SourceInventoryError) else "source_io_error"}))
        return 1
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
