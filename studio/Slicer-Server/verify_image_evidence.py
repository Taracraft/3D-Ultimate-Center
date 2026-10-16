"""Bind source-preflight image evidence to reviewed sources and optional Linux evidence.

Read-only and offline: never import supplied source files, extract archives,
start an engine, run Docker, install software, or approve a product release.
The expected commit and manifest digest must come from a trusted delivery record.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

import prepare_context
import target_image_sbom
import linux_test_evidence

LIMIT = 16 * 1024 * 1024
EVIDENCE_LIMIT = 8 * 1024 * 1024
NAMES = frozenset({"image-build-result.json", "resource-layout.json", "source-check.json", "target-image-sbom.json"})
BUILD_FALSE = frozenset({"engine_binaries_included", "engine_executed", "services_started", "host_mounts_used", "image_pushed", "clean_linux_installation_verified", "production_approved"})
BUILD_FIELDS = BUILD_FALSE | {
    "schema", "source_commit", "run_id", "image_id", "base_image", "platform",
    "base_reference_sha256", "dockerfile_sha256", "source_manifest_sha256",
    "context_manifest_sha256", "image_build_passed", "target_inventory_complete",
    "package_count", "required_package_count", "resource_links_verified", "evidence_files",
}
MANIFEST_FALSE = {"container_deploy_ready", "engine_binaries_included", "github_wiki_published", "native_deploy_ready", "private_runtime_data_included", "production_approved"}
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40 = re.compile(r"[0-9a-f]{40}")


class EvidenceError(ValueError):
    """A bounded diagnostic code; never expose supplied document text."""


def require(condition, code):
    if not condition:
        raise EvidenceError(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value, code):
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None and value != "0" * 64, code)
    return value


def count(value, code, maximum=10000):
    require(type(value) is int and 0 < value <= maximum, code)
    return value


def fields(value, expected, code):
    require(isinstance(value, dict) and set(value) == set(expected), code)
    return value


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def reject_number(_):
    raise EvidenceError("unsupported_json_number")


def document(raw):
    require(len(raw) <= EVIDENCE_LIMIT, "json_size_limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject_number, parse_float=reject_number)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, OverflowError) as exc:
        raise EvidenceError("invalid_json") from exc
    require(isinstance(value, dict), "json_object_required")
    return value


def safe_path(path):
    path = Path(path).absolute()
    for parent in [path, *path.parents]:
        require(not parent.is_symlink() and not getattr(parent, "is_junction", lambda: False)(), "linked_input")
    return path


def read_file(path, maximum=LIMIT):
    path = safe_path(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "regular_input_required")
    require(before.st_size <= maximum, "input_size_limit")
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened), "input_changed")
        data = stream.read(maximum + 1)
        after_open = os.fstat(stream.fileno())
    after = path.stat()
    require(len(data) == before.st_size and identity(before) == identity(after) and identity(opened) == identity(after_open), "input_changed")
    return data


def relative_name(name):
    require(isinstance(name, str) and name and not any(c in name for c in "\\:\x00"), "unsafe_source_path")
    part = PurePosixPath(name)
    require(not part.is_absolute() and part.as_posix() == name and ".." not in part.parts, "unsafe_source_path")
    return name


def load_evidence(path):
    path = safe_path(path)
    if path.is_dir():
        require({item.name for item in path.iterdir()} == NAMES, "evidence_members_mismatch")
        return {name: read_file(path / name, EVIDENCE_LIMIT) for name in sorted(NAMES)}
    raw = read_file(path, EVIDENCE_LIMIT)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            require(len(infos) == len(NAMES) and {i.filename for i in infos} == NAMES, "evidence_members_mismatch")
            require(sum(i.file_size for i in infos) <= EVIDENCE_LIMIT, "evidence_size_limit")
            result = {}
            for info in infos:
                require(not info.flag_bits & 1 and not info.is_dir(), "unsupported_zip_member")
                require(info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}, "unsupported_zip_member")
                require(stat.S_IFMT(info.external_attr >> 16) in {0, stat.S_IFREG}, "linked_zip_member")
                with archive.open(info) as member:
                    value = member.read(EVIDENCE_LIMIT + 1)
                require(len(value) == info.file_size and len(value) <= EVIDENCE_LIMIT, "evidence_size_limit")
                result[info.filename] = value
            return result
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise EvidenceError("invalid_evidence_zip") from exc


def verify_sources(root, expected_manifest):
    root = safe_path(root)
    raw = read_file(root / "slicer-source-manifest.json", EVIDENCE_LIMIT)
    require(sha(raw) == digest(expected_manifest, "invalid_expected_manifest"), "source_manifest_mismatch")
    value = document(raw)
    fields(value, MANIFEST_FALSE | {"schema", "component", "files", "payload_files", "source_paths", "scope"}, "source_manifest_fields")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["component"] == "ultimate-slicer-server", "source_manifest_schema")
    require(all(value[key] is False for key in MANIFEST_FALSE), "source_release_flags")
    rows = value["files"]
    require(isinstance(rows, list) and len(rows) == count(value["payload_files"], "source_file_count"), "source_file_count")
    seen, data, origins = set(), {}, set()
    total_bytes = 0
    for row in rows:
        fields(row, {"path", "source_path", "bytes", "sha256", "mode"}, "source_row_fields")
        name = relative_name(row["path"])
        require(name not in seen and name != "slicer-source-manifest.json", "duplicate_source_path")
        seen.add(name)
        require(row["mode"] in {"100644", "100755"}, "source_file_mode")
        require(type(row["bytes"]) is int and 0 <= row["bytes"] <= LIMIT, "source_file_size")
        total_bytes += row["bytes"]
        require(total_bytes <= 128 * 1024 * 1024, "source_total_size_limit")
        source = read_file(root / name)
        require(len(source) == row["bytes"] and sha(source) == digest(row["sha256"], "source_hash_invalid"), "source_bytes_mismatch")
        data[name] = source
        if row["source_path"] is not None:
            origins.add(relative_name(row["source_path"]))
    require(len(origins) == count(value["source_paths"], "source_origin_count"), "source_origin_count")
    for row in rows:
        if row["source_path"] is not None:
            require(row["source_path"] in data and data[row["path"]] == data[row["source_path"]], "source_alias_mismatch")
    needed = {"Slicer-Server/Dockerfile", "Slicer-Server/TARGET_BASE_REFERENCE.json", "Slicer-Server/TARGET_IMAGE_REFERENCE.json"}
    require(needed <= set(data), "source_reference_missing")
    return data


def verify_bundle(*, source_root, evidence_path, expected_commit, expected_manifest, linux_path=None, expected_package_archive=None, expected_package_manifest=None):
    require(isinstance(expected_commit, str) and HEX40.fullmatch(expected_commit) is not None and expected_commit != "0" * 40, "invalid_expected_commit")
    provided = (linux_path is not None, expected_package_archive is not None, expected_package_manifest is not None)
    require(not any(provided) or all(provided), "linux_arguments_incomplete")
    sources = verify_sources(source_root, expected_manifest)
    raw = load_evidence(evidence_path)
    values = {name: document(value) for name, value in raw.items()}
    build = fields(values["image-build-result.json"], BUILD_FIELDS, "build_fields")
    require(type(build["schema"]) is int and build["schema"] == 1, "build_schema")
    require(build["source_commit"] == expected_commit, "source_commit_mismatch")
    require(build["source_manifest_sha256"] == expected_manifest, "build_source_manifest_mismatch")
    require(isinstance(build["run_id"], str) and re.fullmatch(r"[1-9][0-9]{0,24}", build["run_id"]) is not None, "invalid_run_id")
    require(build["platform"] == "linux/amd64", "platform_mismatch")
    require(build["image_build_passed"] is True and build["target_inventory_complete"] is True, "build_not_passed")
    require(all(build[key] is False for key in BUILD_FALSE), "unsupported_build_scope")
    image = build["image_id"]
    require(isinstance(image, str) and image.startswith("sha256:"), "invalid_image_id")
    image_digest = digest(image[7:], "invalid_image_id")
    count(build["package_count"], "invalid_package_count")
    count(build["required_package_count"], "invalid_required_package_count")
    require(type(build["resource_links_verified"]) is int and build["resource_links_verified"] == 12, "resource_count_mismatch")

    rows = build["evidence_files"]
    require(isinstance(rows, list) and len(rows) == 3, "evidence_index_mismatch")
    seen = set()
    for row in rows:
        fields(row, {"path", "bytes", "sha256"}, "evidence_row_fields")
        name = row["path"]
        require(isinstance(name, str) and name in NAMES - {"image-build-result.json"} and name not in seen, "evidence_index_mismatch")
        seen.add(name)
        require(type(row["bytes"]) is int and row["bytes"] == len(raw[name]) and row["sha256"] == sha(raw[name]), "evidence_bytes_mismatch")

    base = document(sources["Slicer-Server/TARGET_BASE_REFERENCE.json"])
    reference_raw = sources["Slicer-Server/TARGET_IMAGE_REFERENCE.json"]
    reference = document(reference_raw)
    docker_hash = sha(sources["Slicer-Server/Dockerfile"])
    require(build["dockerfile_sha256"] == docker_hash == reference.get("dockerfile_sha256"), "dockerfile_reference_mismatch")
    require(build["base_reference_sha256"] == sha(sources["Slicer-Server/TARGET_BASE_REFERENCE.json"]), "base_reference_mismatch")
    require(type(base.get("schema")) is int and base["schema"] == 1 and base.get("platform") == "linux/amd64", "base_schema")
    require(base.get("production_approved") is False and base.get("target_image_verified") is False, "base_release_flags")
    platform_digest = digest(base.get("platform_manifest_sha256"), "base_digest_invalid")
    expected_base = "docker.io/library/python@sha256:" + platform_digest
    require(base.get("base_image") == expected_base == build["base_image"], "base_image_mismatch")
    require(type(reference.get("schema")) is int and reference["schema"] == 1 and reference.get("platform") == build["platform"], "reference_schema")
    require(reference.get("production_approved") is False and reference.get("target_image_verified") is False, "reference_release_flags")
    require(type(reference.get("required_package_count")) is int and reference["required_package_count"] == build["required_package_count"], "required_package_count_mismatch")

    inventory = fields(values["target-image-sbom.json"], {"schema", "kind", "base_image", "image_id", "reference_sha256", "required_packages", "package_count", "packages", "target_inventory_complete", "production_approved", "runtime_approved", "limitations"}, "inventory_fields")
    require(type(inventory["schema"]) is int and inventory["schema"] == 1, "inventory_schema")
    require(type(inventory["package_count"]) is int and inventory["package_count"] == build["package_count"], "package_count_mismatch")
    require(inventory["base_image"] == expected_base and inventory["image_id"] == image, "inventory_image_mismatch")
    require(isinstance(inventory["required_packages"], list) and len(inventory["required_packages"]) == build["required_package_count"], "required_package_count_mismatch")
    target_image_sbom.verify(inventory, Path(source_root) / "Slicer-Server/TARGET_IMAGE_REFERENCE.json")
    require(inventory["reference_sha256"] == sha(reference_raw), "inventory_reference_mismatch")

    # The trusted, adjacent context builder only reads supplied source bytes.
    payload, context = prepare_context.collect(Path(source_root))
    require(all(row["source"] in sources and payload[row["path"]] == sources[row["source"]] for row in context["files"]), "context_source_not_manifested")
    require(sha(payload["context-manifest.json"]) == build["context_manifest_sha256"], "context_manifest_mismatch")
    check = fields(values["source-check.json"], {"source_integrity", "verified_files", "version", "api_protocol", "container_deploy_ready", "engine_included", "installation_performed", "worker_started"}, "source_check_fields")
    require(check["source_integrity"] == "verified" and type(check["verified_files"]) is int and check["verified_files"] == len(context["files"]), "source_check_mismatch")
    require(type(check["api_protocol"]) is int and check["api_protocol"] == context["api_protocol"] and check["version"] == context["version"], "source_identity_mismatch")
    require(all(check[k] is False for k in ("container_deploy_ready", "engine_included", "installation_performed", "worker_started")), "source_check_scope")
    layout = fields(values["resource-layout.json"], {"engine_executed", "engine_readiness_verified", "image_resource_links", "links_verified"}, "layout_fields")
    require(layout["engine_executed"] is False and layout["engine_readiness_verified"] is False and layout["image_resource_links"] == "verified" and type(layout["links_verified"]) is int and layout["links_verified"] == build["resource_links_verified"], "layout_mismatch")

    linux = {"status": "not_run", "provided": False, "image_bound_phases": [], "evidence_contract_complete": False}
    if linux_path is not None:
        linux_raw = read_file(linux_path, linux_test_evidence.MAX_BYTES)
        linux_doc = document(linux_raw)
        require(type(linux_doc.get("schema")) is int and linux_doc["schema"] == linux_test_evidence.SCHEMA, "linux_schema")
        summary = linux_test_evidence.validate_document(linux_doc, digest(expected_package_archive, "invalid_package_archive"), digest(expected_package_manifest, "invalid_package_manifest"))
        require(linux_doc["host"]["architecture"] in {"amd64", "x86_64"}, "linux_architecture_mismatch")
        mapped = {p["id"]: p for p in linux_doc["phases"]}
        bound = []
        for phase, keys in {"compose": ("image_sha256",), "runtime": ("api_image_sha256", "worker_image_sha256"), "upgrade": ("old_image_sha256",), "rollback": ("restored_image_sha256",)}.items():
            if mapped[phase]["status"] == "passed":
                require(all(mapped[phase]["checks"][k] == image_digest for k in keys), "linux_image_mismatch")
                bound.append(phase)
        linux = {"provided": True, "status": "complete" if summary["testserver_acceptance_complete"] else ("blocked" if summary["blocked_phases"] else "partial"), "evidence_contract_complete": summary["testserver_acceptance_complete"], "image_bound_phases": bound, "sha256": sha(linux_raw), "passed_phases": summary["passed_phases"], "blocked_phases": summary["blocked_phases"], "not_run_phases": summary["not_run_phases"]}
    # Detect changed source files, references or evidence across verification.
    require(verify_sources(source_root, expected_manifest) == sources, "source_changed_during_verification")
    require(load_evidence(evidence_path) == raw, "evidence_changed_during_verification")
    if linux_path is not None:
        require(read_file(linux_path, linux_test_evidence.MAX_BYTES) == linux_raw, "linux_changed_during_verification")
    return {"schema": 1, "kind": "ultimate-slicer-image-evidence-binding", "image_source_binding_verified": True, "source_commit": expected_commit, "source_manifest_sha256": expected_manifest, "source_files_verified": len(sources), "context_manifest_sha256": build["context_manifest_sha256"], "image_id": image, "base_image": expected_base, "run_id": build["run_id"], "package_count": build["package_count"], "required_package_count": build["required_package_count"], "evidence_sha256": {n: sha(raw[n]) for n in sorted(raw)}, "linux_evidence": linux, "production_approved": False, "release_complete": False, "engine_executed": False, "installation_performed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--linux-evidence", type=Path)
    parser.add_argument("--expected-package-archive-sha256")
    parser.add_argument("--expected-package-manifest-sha256")
    args = parser.parse_args(argv)
    try:
        result = verify_bundle(source_root=args.source_root, evidence_path=args.evidence, expected_commit=args.expected_commit, expected_manifest=args.expected_manifest_sha256, linux_path=args.linux_evidence, expected_package_archive=args.expected_package_archive_sha256, expected_package_manifest=args.expected_package_manifest_sha256)
        print(json.dumps(result, sort_keys=True))
        return 2 if result["linux_evidence"]["provided"] and not result["linux_evidence"]["evidence_contract_complete"] else 0
    except (EvidenceError, target_image_sbom.EvidenceError, prepare_context.ContextError, linux_test_evidence.EvidenceError, OSError, KeyError, TypeError, ValueError, RecursionError) as exc:
        code = str(exc) if type(exc) is EvidenceError else "input_contract_rejected"
        parser.exit(1, "Image evidence rejected: " + code + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
