"""Byte-exact Git delivery contract. No deployment, engine or network calls."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

PROTECTED_TREE = "83eee0b12ba828dd1de1e3c9ba83ca2af45e66df"
MANIFEST = "studio-delivery-manifest.json"
MAX_FILES = 10000
MAX_MANIFEST = 4 * 1024 * 1024
MAX_FILE = 32 * 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}")
PRIVATE_PARTS = {".git", ".venv", "node_modules", "__pycache__", "backups",
                 "backup", ".runtime", ".test-results", ".test-build",
                 "uploads", "jobs", "secrets", ".codex-backups", ".task-backups"}
PRIVATE_NAMES = {"AGENTS.md", "LIVE_WORKLOG.md", "secrets.yaml", "options.json",
                 "api-token", "auth", "token"}
REVIEW_NAMES = ("infrastructure", "credentials", "licenses", "isolated_candidate")
HOST_PREFIX = "studio/deploy/homeassistant/host/3d-printer-slicing-server/"
HOST_RUNTIME_NAMES = (
    "server.py", "job_control.py", "dispatch-job.sh", "progress-pipe-reader.py",
    "refresh-state.sh", "append-slicing-journal.sh", "bambu_lab_h2s_04.json",
    "profiles/printers/bambu_lab_a1_04.json", "profiles/printers/bambu_lab_h2s_04.json",
    "SHA256SUMS", "DEPENDENCY-SHA256SUMS",
)
HOST_RUNTIME_PATHS = frozenset(HOST_PREFIX + name for name in HOST_RUNTIME_NAMES)
# Exact individually reviewed source files required by synthetic native contract tests.
# This permits source delivery only; it is not installation or service approval.
NATIVE_TEST_SOURCE_PATHS = frozenset((
    "studio/deploy/homeassistant/host/release/fresh-install-preflight.sh",
    HOST_PREFIX + "deploy-native-slicer.sh",
    HOST_PREFIX + "systemd/3d-printer-slicing-server.service",
    HOST_PREFIX + "systemd/3d-printer-slicing-dispatch.service",
    HOST_PREFIX + "systemd/3d-printer-slicing-dispatch.timer",
    HOST_PREFIX + "systemd/3d-printer-slicing-refresh.service",
    HOST_PREFIX + "systemd/3d-printer-slicing-refresh.timer",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-server.service",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-dispatch.service",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-dispatch.timer",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-refresh.service",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-refresh.timer",
))

class DeliveryError(ValueError):
    pass

def fail(condition: bool, reason: str) -> None:
    if not condition:
        raise DeliveryError(reason)

def no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        fail(key not in value, "duplicate_json_key")
        value[key] = item
    return value

def linked(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()

def relative_name(name) -> str:
    fail(isinstance(name, str) and 0 < len(name) <= 512, "invalid_path")
    fail("\\" not in name and "\x00" not in name and ":" not in name, "invalid_path")
    parts = name.split("/")
    fail(all(p not in {"", ".", ".."} for p in parts), "invalid_path")
    fail(not PurePosixPath(name).is_absolute(), "invalid_path")
    return name

def forbidden(name: str) -> bool:
    parts = name.split("/")
    return (any(p.casefold() in {s.casefold() for s in PRIVATE_PARTS} for p in parts)
            or parts[-1] in PRIVATE_NAMES
            or any(re.search(r"\.(?:bak|backup|before)(?:[._-]|$)", p, re.I) for p in parts)
            or name.startswith("studio/docs/")
            or (name.startswith("studio/deploy/homeassistant/host/")
                and name not in HOST_RUNTIME_PATHS and name not in NATIVE_TEST_SOURCE_PATHS)
            or any(re.fullmatch(r"studio-v\d+|ultimate_3d_studio_v\d+|3d-studio-v\d+",p,re.I) for p in parts)
            or parts[-1].lower().endswith((".pem", ".key", ".deb", ".appimage"))
            or (parts[-1].lower().endswith((".service", ".timer")) and name not in NATIVE_TEST_SOURCE_PATHS)
            or name in {"studio/tests/large_model.stl", "studio/tests/large_model_test.stl"})

def checked_file(root: Path, name: str) -> Path:
    path = root
    for part in name.split("/"):
        path /= part
        fail(not linked(path), "linked_delivery_path")
    fail(path.is_file(), "missing_delivery_file")
    fail(path.stat().st_size <= MAX_FILE, "delivery_file_too_large")
    return path

def verify(root: Path, manifest: dict, tracked: set[str], protected_tree: str) -> dict:
    fail(root.is_dir() and not linked(root), "invalid_root")
    fail(isinstance(manifest, dict), "invalid_manifest")
    fail(set(manifest) == {"schema", "reviewed_for_git_delivery", "production_approved",
                          "protected_component_tree", "review_evidence", "files"}, "manifest_fields")
    fail(type(manifest["schema"]) is int and manifest["schema"] == 1, "manifest_schema")
    fail(manifest["reviewed_for_git_delivery"] is True, "git_delivery_not_reviewed")
    fail(manifest["production_approved"] is False, "test_delivery_is_not_production_approval")
    fail(protected_tree == PROTECTED_TREE == manifest["protected_component_tree"],
         "protected_component_changed")
    evidence = manifest["review_evidence"]
    fail(isinstance(evidence, dict) and set(evidence) == set(REVIEW_NAMES), "review_evidence_fields")
    for item in evidence.values():
        fail(isinstance(item, dict) and set(item) == {"verified", "sha256"}, "review_evidence_fields")
        fail(item["verified"] is True and isinstance(item["sha256"], str)
             and HEX.fullmatch(item["sha256"]) is not None and item["sha256"] != "0" * 64,
             "review_evidence_missing")
    rows = manifest["files"]
    fail(isinstance(rows, list) and 0 < len(rows) <= MAX_FILES, "manifest_file_count")
    names = set()
    folded = set()
    for row in rows:
        fail(isinstance(row, dict) and set(row) == {"path", "bytes", "sha256"}, "file_record_fields")
        name = relative_name(row["path"])
        fail(name != MANIFEST and name not in names and name.casefold() not in folded, "duplicate_or_self_path")
        fail(not forbidden(name), "private_or_retired_delivery_path")
        names.add(name)
        folded.add(name.casefold())
        fail(type(row["bytes"]) is int and 0 <= row["bytes"] <= MAX_FILE, "invalid_size")
        fail(isinstance(row["sha256"], str) and HEX.fullmatch(row["sha256"]) is not None, "invalid_sha256")
        path = checked_file(root, name)
        data = path.read_bytes()
        fail(len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"], "delivery_hash_mismatch")
    fail(names | {MANIFEST} == tracked, "tracked_delivery_scope_mismatch")
    return {"verified": True, "files": len(names), "production_approved": False,
            "protected_component_unchanged": True}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        root = args.root.absolute()
        path = checked_file(root, MANIFEST)
        fail(path.stat().st_size <= MAX_MANIFEST, "manifest_too_large")
        data = path.read_bytes()
        manifest = json.loads(data, object_pairs_hook=no_duplicates)
        raw = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"])
        tracked = {p for p in raw.decode("utf-8").split("\0") if p}
        tree = subprocess.check_output(["git", "-C", str(root), "rev-parse",
                                      "HEAD:homeassistant/custom_components/printer_control_center"],
                                     stderr=subprocess.DEVNULL).decode("ascii").strip()
        print(json.dumps(verify(root, manifest, tracked, tree), sort_keys=True))
        return 0
    except (DeliveryError, OSError, ValueError, subprocess.SubprocessError):
        print(json.dumps({"verified": False, "error": "delivery_contract_failed"}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
