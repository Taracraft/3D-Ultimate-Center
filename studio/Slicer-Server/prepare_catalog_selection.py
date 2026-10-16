"""Project verified engine bundle metadata into the existing installer FileSpec contract.

No downloads, activation, engine execution or edits to the shipped catalog.
The Cura base definition is a resource in the selection, without changing any
archive byte or the original bundle manifest. See ENGINE_CATALOG.md.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

import build_engine_bundle as bundle
import engine_catalog as catalog
from package_staging import _target_contract

MAX_MANIFEST_BYTES = 16 * 1024 * 1024
CURA_BASE = "resources/definitions/fdmprinter.def.json"
FLAGS = {"engine_executed", "runtime_approved", "license_review_complete", "release_approved"}
FIELDS = FLAGS | {"schema", "engine", "version", "system", "architecture", "upstream_archives", "files"}
ARTIFACT_FIELDS = {"id", "component_version", "url", "sha256", "size_bytes", "format", "license", "source_url", "source_revision"}


class SelectionError(ValueError):
    """Fixed diagnostic code; no raw input values in CLI errors."""


def require(value, code):
    if not value:
        raise SelectionError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None
            and value != "0" * 64, "invalid_expected_digest")
    return value


def unique(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, "duplicate_json_key")
        result[name] = value
    return result


def invalid_number(_):
    raise SelectionError("non_integer_json_number")


def project_manifest(raw, expected_sha256):
    """Return a detached proposal from an externally pinned original manifest.

    Status flags must describe the existing unapproved source bundles. A future
    approved distribution needs its own reviewed publication record; changing
    these flags is not a release workflow.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MAX_MANIFEST_BYTES, "manifest_size")
    require(digest(raw) == pinned(expected_sha256), "manifest_digest_mismatch")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                           parse_float=invalid_number, parse_constant=invalid_number)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SelectionError("invalid_manifest_json") from exc
    require(type(value) is dict and set(value) == FIELDS, "manifest_fields")
    require(type(value["schema"]) is int and value["schema"] == 1, "manifest_schema")
    require(value["system"] == "linux" and value["architecture"] == "amd64", "unsupported_platform")
    require(all(value[key] is False for key in FLAGS), "unsupported_bundle_scope")
    require(type(value["files"]) is list and 1 <= len(value["files"]) <= bundle.MAX_FILES, "manifest_file_count")
    original = value["files"]
    projected, adjustments = [], []
    for item in original:
        require(type(item) is dict and set(item) == {"path", "bytes", "sha256", "role", "executable"}, "manifest_file_fields")
        selected = copy.deepcopy(item)
        if value["engine"] == "curaengine" and item["path"] == CURA_BASE:
            require(item["role"] in {"profiles", "resources"} and item["executable"] is False
                    and type(item["bytes"]) is int and item["bytes"] > 0, "invalid_cura_base")
            if item["role"] == "profiles":
                selected["role"] = "resources"
                adjustments.append({"path": CURA_BASE, "from": "profiles", "to": "resources",
                                    "bytes": item["bytes"], "sha256": item["sha256"]})
        projected.append({**selected, "root": "payload", "source": item["path"]})
    if value["engine"] == "curaengine":
        require(sum(item["path"] == CURA_BASE for item in projected) == 1, "missing_cura_base")
    inventory = {"schema": 1, "engine": value["engine"], "version": value["version"],
                 "upstream_archives": copy.deepcopy(value["upstream_archives"]), "files": projected}
    # Reuse all existing bundle limits, path-collision, entrypoint and role checks.
    bundle.validate(inventory)
    files = [{"path": item["path"], "size_bytes": item["bytes"], "sha256": item["sha256"],
              "role": item["role"], "executable": item["executable"]}
             for item in sorted(projected, key=lambda row: row["path"])]
    parsed = tuple(catalog._file(row) for row in files)
    _target_contract(parsed)
    require(len(files) == len(original), "selection_coverage_changed")
    roles = {role: sum(row["role"] == role for row in files) for role in sorted(catalog.ROLES)}
    return {"schema": 1, "kind": "ultimate-engine-catalog-file-selection",
            "engine": value["engine"], "version": value["version"], "system": "linux", "architecture": "amd64",
            "source_manifest_sha256": expected_sha256, "upstream_archives": inventory["upstream_archives"],
            "files": files, "file_count": len(files), "installed_bytes": sum(row["size_bytes"] for row in files),
            "role_counts": roles, "role_adjustments": adjustments,
            "archive_bytes_changed": False, "catalog_updated": False,
            "license_review_complete": False, "runtime_approved": False, "release_approved": False}


def bind_release(raw, expected_manifest_sha256, artifact):
    """Validate proposed files with explicit, independently reviewed artifact data.

    Returns the existing Release type, not a publication approval. The caller
    remains responsible for download availability and source/license obligations.
    No default URLs, revision guesses or approval flag changes are supplied.
    """
    require(type(artifact) is dict and set(artifact) == ARTIFACT_FIELDS, "artifact_metadata_fields")
    metadata = copy.deepcopy(artifact)
    selection = project_manifest(raw, expected_manifest_sha256)
    require(metadata["component_version"] == selection["version"] and metadata["format"] == "tar.gz", "bundle_artifact_mismatch")
    pinned(metadata["sha256"])
    return catalog._release({"engine": selection["engine"], "version": selection["version"],
        "system": selection["system"], "architecture": selection["architecture"],
        "artifacts": [{**metadata, "files": selection["files"]}]})


def snapshot(path, maximum):
    path = bundle.safe_local(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum, "unsafe_input_file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened), "input_changed")
        raw = stream.read(maximum + 1)
        require(bundle.identity(opened) == bundle.identity(os.fstat(stream.fileno())), "input_changed")
    require(len(raw) == before.st_size and bundle.identity(before) == bundle.identity(path.stat()), "input_changed")
    return raw


def prepare(manifest_path, expected_sha256, output):
    """Write one new external proposal directory; never replace existing files."""
    source = bundle.safe_local(manifest_path)
    raw = snapshot(source, MAX_MANIFEST_BYTES)
    result = project_manifest(raw, expected_sha256)
    output = bundle.safe_local(output)
    code_root = Path(__file__).resolve().parents[1]
    require(not output.exists(), "output_exists")
    require(output != code_root and code_root not in output.parents, "output_inside_source")
    require(output != source and output not in source.parents, "output_contains_input")
    require(snapshot(source, MAX_MANIFEST_BYTES) == raw, "input_changed")
    payload = bundle.canonical(result)
    output.mkdir(parents=True, exist_ok=False)
    target = output / "file-selection.json"
    with target.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    require(snapshot(target, MAX_MANIFEST_BYTES) == payload and snapshot(source, MAX_MANIFEST_BYTES) == raw, "selection_readback_failed")
    return {"schema": 1, "engine": result["engine"], "file_count": result["file_count"],
            "installed_bytes": result["installed_bytes"], "role_counts": result["role_counts"],
            "role_adjustments": result["role_adjustments"], "selection_sha256": digest(payload),
            "source_manifest_sha256": expected_sha256, "catalog_updated": False,
            "archive_verified": False, "engine_executed": False, "release_approved": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.manifest, args.expected_manifest_sha256, args.output)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        print(json.dumps({"ok": False, "error": "catalog_selection_rejected"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
