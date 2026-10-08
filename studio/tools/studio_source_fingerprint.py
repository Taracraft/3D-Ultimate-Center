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
              "build_frontend.mjs", "build_studio_core.mjs", "run_frontend_logic_tests.mjs",
              "run_frontend_tests.mjs", "run_python_tests.py", "connector_studio_gate.py")
EXCLUDED_PARTS = frozenset({".git", "node_modules", "__pycache__", "backups", "backup", "dist",
                           "data", "run", "runtime", "engines", "uploads", "output", "logs"})
EXCLUDED_NAMES = frozenset({"config.json", "options.json", "secrets.yaml", "token", "auth"})
RECOVERY = re.compile(r"(?:\.(?:bak|backup|before)(?:[._-]|$)|~$)", re.I)
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_FILES = 5000

RETIRED_V6_FRONTEND = frozenset({
    "jobs-workspaces-v6.ts",
    "makerworld-detail-dialog-v6.ts",
    "makerworld-v6-adapter.ts",
    "makerworld-v6-adapter2.ts",
    "makerworld-workspace-v6.ts",
    "v6-action-dialog.ts",
    "v6-api.ts",
    "v6-context-menu.ts",
    "v6-entry.ts",
})
P1_RETIRED_MARKER = "Retired by the P1 namespace migration on 2026-10-07."
P1_RETIRED_TREE_MARKER = ".p1-retired-namespace"
RETIRED_V6_TREES = {
    "deploy/homeassistant/custom_components/ultimate_3d_studio_v6":
        "deploy/homeassistant/custom_components/ultimate_3d_studio",
    "deploy/homeassistant/www/3d-studio-v6":
        "deploy/homeassistant/www/3d-studio",
}
RETIRED_V6_PUPPET = {
    "v6-puppet-hosts.service": "studio-puppet-hosts.service",
    "v6-puppet-hosts.sh": "studio-puppet-hosts.sh",
    "v6-puppet-hosts.timer": "studio-puppet-hosts.timer",
}

ACTIVE_NAMESPACE_ROOTS = frozenset({"api", "core", "frontend", "frontend-tests", "tests", "tools", "deploy"})
ACTIVE_NAMESPACE_ALLOWLIST = frozenset({
    "frontend-tests/storage-upgrade.test.ts",
    "tests/test_source_fingerprint.py",
    "tests/test_p1_active_namespace.py",
    "tests/test_studio_native_slicer_only.py",
    "tools/studio_source_fingerprint.py",
})
ACTIVE_NAMESPACE_SUFFIXES = frozenset({".py", ".ts", ".js", ".mjs", ".cjs", ".json", ".sh", ".ps1", ".yaml", ".yml", ".toml", ".md"})
ACTIVE_NAMESPACE_PATTERNS = (
    ("v6_product_token", re.compile(r"(?<![A-Za-z0-9])v6(?![A-Za-z0-9])", re.I)),
    ("v6_class_token", re.compile(r"Ultimate3DStudioV6", re.I)),
    ("double_studio_token", re.compile(r"(?:Ultimate3DStudioStudio|Studio-Studio)", re.I)),
    ("legacy_api_namespace", re.compile(r"printer_control_center/v1", re.I)),
)


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


def _skip_retired_namespace_dir(root: Path, path: Path, relative: Path) -> bool:
    """Skip only explicitly retired P1 namespace trees; active trees fail closed."""
    target = RETIRED_V6_TREES.get(relative.as_posix())
    if target is None:
        return False
    marker = path / P1_RETIRED_TREE_MARKER
    if not marker.is_file() or _link(marker):
        raise SourceInventoryError("active_v6_deploy_tree_in_publish_scope")
    text = marker.read_text(encoding="utf-8-sig")
    if P1_RETIRED_MARKER not in text or f"Active tree: {target}" not in text:
        raise SourceInventoryError("active_v6_deploy_tree_in_publish_scope")
    active = root / Path(target)
    if not active.is_dir() or _link(active):
        raise SourceInventoryError("retired_v6_tree_missing_active_replacement")
    return True


def _skip_retired_namespace_file(path: Path, relative: Path) -> bool:
    """Skip only explicit P1 retirement stubs; active legacy files fail closed."""
    if relative.parts and relative.parts[0] == "tests" and re.fullmatch(r"test_v6_.*\.py", path.name, re.I):
        text = path.read_text(encoding="utf-8-sig")
        if (
            P1_RETIRED_MARKER in text
            and "__test__ = False" in text
            and "Active contract moved to test_studio_" in text
        ):
            return True
        raise SourceInventoryError("active_v6_test_in_publish_scope")

    if relative.parts and relative.parts[0] == "frontend" and path.name.casefold() in RETIRED_V6_FRONTEND:
        text = path.read_text(encoding="utf-8-sig")
        if P1_RETIRED_MARKER in text and "Active module:" in text:
            return True
        raise SourceInventoryError("active_v6_frontend_in_publish_scope")

    if (
        relative.parent.as_posix() == "deploy/homeassistant/host/puppet"
        and path.name.casefold() in RETIRED_V6_PUPPET
    ):
        active_name = RETIRED_V6_PUPPET[path.name.casefold()]
        text = path.read_text(encoding="utf-8-sig")
        if P1_RETIRED_MARKER in text and f"Active file: {active_name}" in text:
            return True
        raise SourceInventoryError("active_v6_puppet_in_publish_scope")

    return False


def _active_namespace_violation(path: Path, relative: Path) -> str | None:
    """Return one active product namespace violation, preserving explicit history."""
    rel = relative.as_posix()
    if rel in ACTIVE_NAMESPACE_ALLOWLIST:
        return None
    if rel == "README.md":
        pass
    elif not relative.parts or relative.parts[0] not in ACTIVE_NAMESPACE_ROOTS:
        return None
    if relative.parts and relative.parts[0] == "docs":
        return None
    if path.suffix.lower() not in ACTIVE_NAMESPACE_SUFFIXES and rel != "README.md":
        return None
    text = path.read_text(encoding="utf-8-sig")
    for label, pattern in ACTIVE_NAMESPACE_PATTERNS:
        if pattern.search(text):
            return f"active_namespace_content:{label}:{rel}"
    return None


def source_paths(root: Path) -> list[Path]:
    if not root.is_dir() or _link(root):
        raise SourceInventoryError("invalid_source_root")
    result = []
    namespace_violations: list[str] = []
    for name in ROOT_FILES:
        path = root / name
        if path.exists() or path.is_symlink():
            if _link(path):
                raise SourceInventoryError("linked_source")
            violation = _active_namespace_violation(path, Path(name))
            if violation:
                namespace_violations.append(violation)
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
                child_path = current / child
                relative_dir = child_path.relative_to(root)
                if _skip_retired_namespace_dir(root, child_path, relative_dir):
                    continue
                if child.startswith(".") or child.casefold() in EXCLUDED_PARTS or RECOVERY.search(child):
                    continue
                if _link(child_path):
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
                relative = path.relative_to(root)
                if _skip_retired_namespace_file(path, relative):
                    continue
                violation = _active_namespace_violation(path, relative)
                if violation:
                    namespace_violations.append(violation)
                result.append(path)
                if len(result) > MAX_FILES:
                    raise SourceInventoryError("source_count_limit")
    if namespace_violations:
        raise SourceInventoryError(";".join(namespace_violations[:200]))
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
