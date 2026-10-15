"""Verify a sanitized evidence bundle from the isolated Linux test server."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re


SCHEMA = 5
MAX_BYTES = 256 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}")
SAFE_WORD = re.compile(r"[a-z0-9][a-z0-9._+-]{0,63}")
FORBIDDEN_KEYS = re.compile(
    r"(?:^|_)(?:token|secret|password|private_key|authorization|cookie|access_code)(?:_|$)",
    re.IGNORECASE,
)
PRIVATE_MARKERS = (
    b"-----BEGIN " + b"PRIVATE KEY-----",
    b"-----BEGIN RSA " + b"PRIVATE KEY-----",
    b"-----BEGIN EC " + b"PRIVATE KEY-----",
    b"-----BEGIN OPENSSH " + b"PRIVATE KEY-----",
)
SAFE_NEGATIVE_FIELDS = {
    "secret_in_argv_or_env",
    "private_key_exported",
    "browser_secret_absent",
}

PHASE_CHECKS = {
    "package": (
        "sidecar_verified",
        "manifest_verified",
        "extracted_verified",
    ),
    "clean_host": (
        "inventory_complete",
        "native_units",
        "native_markers",
        "native_processes",
        "slicer_containers",
        "clean",
    ),
    "compose": (
        "config_valid",
        "local_image_digest_verified",
        "image_sha256",
        "pull_policy_never",
        "service_user_65532",
        "read_only_root",
        "cap_drop_all",
        "no_new_privileges",
        "docker_socket_absent",
    ),
    "runtime": (
        "api_present",
        "worker_present",
        "same_image",
        "api_image_sha256",
        "worker_image_sha256",
        "worker_network_none",
        "pid_anchor_verified",
        "maintenance_owned",
        "worker_health_passed",
    ),
    "tls": (
        "certificate_verified",
        "hostname_verified",
        "unauthenticated_status",
        "authenticated_status",
        "secret_in_argv_or_env",
        "private_key_exported",
    ),
    "persistence": (
        "container_restart_verified",
        "host_restart_verified",
        "data_digest_before",
        "data_digest_after",
        "profiles_digest_before",
        "profiles_digest_after",
    ),
    "upgrade": (
        "maintenance_owned",
        "old_image_sha256",
        "new_image_sha256",
        "ready_paused",
        "data_digest_before",
        "data_digest_after",
        "profiles_digest_before",
        "profiles_digest_after",
    ),
    "rollback": (
        "maintenance_owned",
        "old_image_restored",
        "restored_image_sha256",
        "restored_paused",
        "data_digest_before",
        "data_digest_after",
        "profiles_digest_before",
        "profiles_digest_after",
    ),
    "backup_restore": (
        "backup_sha256",
        "restored_to_new_path",
        "original_untouched",
        "source_digest",
        "restored_digest",
        "source_profiles_digest",
        "restored_profiles_digest",
    ),
    "supervisor": (
        "supervisor_healthy",
        "ha_core_docker_socket_absent",
        "ha_core_slicer_mount_absent",
        "backend_https_reachable",
        "browser_secret_absent",
    ),
}
PHASES = tuple(PHASE_CHECKS)


class EvidenceError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError("duplicate_json_key:" + key)
        result[key] = value
    return result


def _exact_dict(value, keys, code):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise EvidenceError(code)
    return value


def _bool(value, code):
    if type(value) is not bool:
        raise EvidenceError(code)
    return value


def _int(value, code, minimum=0, maximum=1_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise EvidenceError(code)
    return value


def _hash(value, code):
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise EvidenceError(code)
    return value


def _word(value, code):
    if not isinstance(value, str) or SAFE_WORD.fullmatch(value) is None:
        raise EvidenceError(code)
    return value


def _scan_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or (
                FORBIDDEN_KEYS.search(key) and key not in SAFE_NEGATIVE_FIELDS
            ):
                raise EvidenceError("forbidden_field")
            _scan_keys(child)
    elif isinstance(value, list):
        for child in value:
            _scan_keys(child)


def canonical_checks(checks: dict) -> bytes:
    return (json.dumps(checks, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def canonical_phase(
    run_sha256: str,
    package: dict,
    host: dict,
    previous_evidence_sha256: str,
    phase_id: str,
    status: str,
    checks: dict,
) -> bytes:
    value = {
        "schema": SCHEMA,
        "run_sha256": run_sha256,
        "package": package,
        "host": host,
        "previous_evidence_sha256": previous_evidence_sha256,
        "phase": {"id": phase_id, "status": status, "checks": checks},
    }
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def phase_digest(
    run_sha256: str,
    package: dict,
    host: dict,
    previous_evidence_sha256: str,
    phase_id: str,
    status: str,
    checks: dict,
) -> str:
    return digest(
        canonical_phase(
            run_sha256,
            package,
            host,
            previous_evidence_sha256,
            phase_id,
            status,
            checks,
        )
    )


def _validate_checks(phase_id: str, checks: dict, passed: bool) -> None:
    _exact_dict(checks, PHASE_CHECKS[phase_id], "invalid_phase_checks:" + phase_id)
    if phase_id == "package":
        values = [_bool(checks[key], "invalid_package_check") for key in PHASE_CHECKS[phase_id]]
        ok = all(values)
    elif phase_id == "clean_host":
        ok = _bool(checks["inventory_complete"], "invalid_inventory_complete")
        counts = [_int(checks[key], "invalid_inventory_count") for key in (
            "native_units", "native_markers", "native_processes", "slicer_containers"
        )]
        ok = ok and all(value == 0 for value in counts) and _bool(checks["clean"], "invalid_clean")
    elif phase_id == "compose":
        image = _hash(checks["image_sha256"], "invalid_compose_digest")
        ok = (
            image != "0" * 64
            and all(
                _bool(checks[key], "invalid_compose_check")
                for key in PHASE_CHECKS[phase_id]
                if key != "image_sha256"
            )
        )
    elif phase_id == "runtime":
        api_image = _hash(checks["api_image_sha256"], "invalid_runtime_digest")
        worker_image = _hash(checks["worker_image_sha256"], "invalid_runtime_digest")
        ok = (
            api_image != "0" * 64
            and api_image == worker_image
            and all(
                _bool(checks[key], "invalid_runtime_check")
                for key in PHASE_CHECKS[phase_id]
                if key not in {"api_image_sha256", "worker_image_sha256"}
            )
        )
    elif phase_id == "tls":
        ok = (
            _bool(checks["certificate_verified"], "invalid_tls_check")
            and _bool(checks["hostname_verified"], "invalid_tls_check")
            and _int(checks["unauthenticated_status"], "invalid_tls_status", 100, 599) == 401
            and _int(checks["authenticated_status"], "invalid_tls_status", 100, 599) == 200
            and not _bool(checks["secret_in_argv_or_env"], "invalid_tls_exposure")
            and not _bool(checks["private_key_exported"], "invalid_tls_exposure")
        )
    elif phase_id == "persistence":
        data_before = _hash(checks["data_digest_before"], "invalid_persistence_digest")
        data_after = _hash(checks["data_digest_after"], "invalid_persistence_digest")
        profiles_before = _hash(checks["profiles_digest_before"], "invalid_persistence_digest")
        profiles_after = _hash(checks["profiles_digest_after"], "invalid_persistence_digest")
        ok = (
            _bool(checks["container_restart_verified"], "invalid_persistence_check")
            and _bool(checks["host_restart_verified"], "invalid_persistence_check")
            and data_before != "0" * 64
            and data_before == data_after
            and profiles_before != "0" * 64
            and profiles_before == profiles_after
        )
    elif phase_id == "upgrade":
        old_image = _hash(checks["old_image_sha256"], "invalid_upgrade_digest")
        new_image = _hash(checks["new_image_sha256"], "invalid_upgrade_digest")
        data_before = _hash(checks["data_digest_before"], "invalid_upgrade_digest")
        data_after = _hash(checks["data_digest_after"], "invalid_upgrade_digest")
        profiles_before = _hash(checks["profiles_digest_before"], "invalid_upgrade_digest")
        profiles_after = _hash(checks["profiles_digest_after"], "invalid_upgrade_digest")
        ok = (
            _bool(checks["maintenance_owned"], "invalid_upgrade_check")
            and old_image != "0" * 64
            and new_image != "0" * 64
            and old_image != new_image
            and _bool(checks["ready_paused"], "invalid_upgrade_check")
            and data_before != "0" * 64
            and data_before == data_after
            and profiles_before != "0" * 64
            and profiles_before == profiles_after
        )
    elif phase_id == "rollback":
        restored_image = _hash(checks["restored_image_sha256"], "invalid_rollback_digest")
        data_before = _hash(checks["data_digest_before"], "invalid_rollback_digest")
        data_after = _hash(checks["data_digest_after"], "invalid_rollback_digest")
        profiles_before = _hash(checks["profiles_digest_before"], "invalid_rollback_digest")
        profiles_after = _hash(checks["profiles_digest_after"], "invalid_rollback_digest")
        ok = (
            _bool(checks["maintenance_owned"], "invalid_rollback_check")
            and _bool(checks["old_image_restored"], "invalid_rollback_check")
            and restored_image != "0" * 64
            and _bool(checks["restored_paused"], "invalid_rollback_check")
            and data_before != "0" * 64
            and data_before == data_after
            and profiles_before != "0" * 64
            and profiles_before == profiles_after
        )
    elif phase_id == "backup_restore":
        backup = _hash(checks["backup_sha256"], "invalid_restore_digest")
        source = _hash(checks["source_digest"], "invalid_restore_digest")
        restored = _hash(checks["restored_digest"], "invalid_restore_digest")
        source_profiles = _hash(checks["source_profiles_digest"], "invalid_restore_digest")
        restored_profiles = _hash(checks["restored_profiles_digest"], "invalid_restore_digest")
        ok = (
            backup != "0" * 64
            and _bool(checks["restored_to_new_path"], "invalid_restore_check")
            and _bool(checks["original_untouched"], "invalid_restore_check")
            and source != "0" * 64
            and source == restored
            and source_profiles != "0" * 64
            and source_profiles == restored_profiles
        )
    else:
        ok = all(_bool(checks[key], "invalid_supervisor_check") for key in PHASE_CHECKS[phase_id])
    if passed and not ok:
        raise EvidenceError("passed_phase_contract_failed:" + phase_id)


def _validate_phase_continuity(mapped: dict) -> None:
    def passed(phase_id: str) -> bool:
        return mapped[phase_id]["status"] == "passed"

    def checks(phase_id: str) -> dict:
        return mapped[phase_id]["checks"]

    def require_equal(code: str, *values: str) -> None:
        if len(set(values)) != 1:
            raise EvidenceError("phase_continuity_mismatch:" + code)

    if passed("compose") and passed("runtime"):
        require_equal(
            "compose_runtime_image",
            checks("compose")["image_sha256"],
            checks("runtime")["api_image_sha256"],
            checks("runtime")["worker_image_sha256"],
        )
    if passed("runtime") and passed("upgrade"):
        require_equal(
            "runtime_upgrade_image",
            checks("runtime")["api_image_sha256"],
            checks("upgrade")["old_image_sha256"],
        )
    if passed("persistence") and passed("upgrade"):
        require_equal(
            "persistence_upgrade_data",
            checks("persistence")["data_digest_after"],
            checks("upgrade")["data_digest_before"],
        )
        require_equal(
            "persistence_upgrade_profiles",
            checks("persistence")["profiles_digest_after"],
            checks("upgrade")["profiles_digest_before"],
        )
    if passed("upgrade") and passed("rollback"):
        require_equal(
            "upgrade_rollback_data",
            checks("upgrade")["data_digest_after"],
            checks("rollback")["data_digest_before"],
        )
        require_equal(
            "upgrade_rollback_profiles",
            checks("upgrade")["profiles_digest_after"],
            checks("rollback")["profiles_digest_before"],
        )
        require_equal(
            "upgrade_rollback_image",
            checks("upgrade")["old_image_sha256"],
            checks("rollback")["restored_image_sha256"],
        )
    if passed("rollback") and passed("backup_restore"):
        require_equal(
            "rollback_restore_data",
            checks("rollback")["data_digest_after"],
            checks("backup_restore")["source_digest"],
        )
        require_equal(
            "rollback_restore_profiles",
            checks("rollback")["profiles_digest_after"],
            checks("backup_restore")["source_profiles_digest"],
        )

def validate_document(document: dict, expected_archive: str, expected_manifest: str) -> dict:
    _scan_keys(document)
    _exact_dict(
        document,
        {"schema", "run_sha256", "package", "host", "phases", "container_deploy_ready"},
        "invalid_document",
    )
    if document["schema"] != SCHEMA:
        raise EvidenceError("unsupported_schema")
    run_sha256 = _hash(document["run_sha256"], "invalid_run_digest")
    if run_sha256 == "0" * 64:
        raise EvidenceError("invalid_run_digest")
    if _bool(document["container_deploy_ready"], "invalid_release_flag") is not False:
        raise EvidenceError("release_flag_rejected")
    package = _exact_dict(document["package"], {"archive_sha256", "manifest_sha256", "verified"}, "invalid_package")
    if _hash(package["archive_sha256"], "invalid_archive_digest") != _hash(expected_archive, "invalid_expected_archive"):
        raise EvidenceError("archive_digest_mismatch")
    if _hash(package["manifest_sha256"], "invalid_manifest_digest") != _hash(expected_manifest, "invalid_expected_manifest"):
        raise EvidenceError("manifest_digest_mismatch")
    if not _bool(package["verified"], "invalid_package_verified"):
        raise EvidenceError("package_not_verified")
    host = _exact_dict(
        document["host"],
        {"host_fingerprint_sha256", "os_id", "os_version", "architecture", "supervisor_present"},
        "invalid_host",
    )
    _hash(host["host_fingerprint_sha256"], "invalid_host_fingerprint")
    _word(host["os_id"], "invalid_os_id")
    _word(host["os_version"], "invalid_os_version")
    _word(host["architecture"], "invalid_architecture")
    _bool(host["supervisor_present"], "invalid_supervisor_presence")
    phases = document["phases"]
    if not isinstance(phases, list) or len(phases) != len(PHASES):
        raise EvidenceError("invalid_phase_count")
    mapped = {}
    previous_evidence_sha256 = run_sha256
    for phase in phases:
        _exact_dict(
            phase,
            {"id", "status", "previous_evidence_sha256", "evidence_sha256", "checks"},
            "invalid_phase",
        )
        phase_id = phase["id"]
        if phase_id not in PHASE_CHECKS or phase_id in mapped:
            raise EvidenceError("invalid_phase_id")
        if phase_id != PHASES[len(mapped)]:
            raise EvidenceError("phase_order_mismatch")
        if phase["status"] not in {"passed", "blocked", "not_run"}:
            raise EvidenceError("invalid_phase_status")
        if _hash(
            phase["previous_evidence_sha256"], "invalid_previous_phase_digest"
        ) != previous_evidence_sha256:
            raise EvidenceError("phase_chain_mismatch:" + phase_id)
        if _hash(phase["evidence_sha256"], "invalid_phase_digest") != phase_digest(
            run_sha256,
            package,
            host,
            previous_evidence_sha256,
            phase_id,
            phase["status"],
            phase["checks"],
        ):
            raise EvidenceError("phase_digest_mismatch:" + phase_id)
        _validate_checks(phase_id, phase["checks"], phase["status"] == "passed")
        mapped[phase_id] = phase
        previous_evidence_sha256 = phase["evidence_sha256"]
    if tuple(mapped) != PHASES:
        raise EvidenceError("phase_order_mismatch")
    sequence_state = "passed"
    for phase_id in PHASES:
        status = mapped[phase_id]["status"]
        if sequence_state == "passed":
            if status == "blocked":
                sequence_state = "blocked"
            elif status == "not_run":
                sequence_state = "not_run"
        elif status != "not_run":
            raise EvidenceError("phase_sequence_invalid:" + phase_id)
    _validate_phase_continuity(mapped)
    passed = [phase_id for phase_id in PHASES if mapped[phase_id]["status"] == "passed"]
    blocked = [phase_id for phase_id in PHASES if mapped[phase_id]["status"] == "blocked"]
    not_run = [phase_id for phase_id in PHASES if mapped[phase_id]["status"] == "not_run"]
    identity = (
        host["host_fingerprint_sha256"],
        host["os_id"],
        host["os_version"],
        host["architecture"],
    )
    if identity[0] == "0" * 64 or any(value == "unknown" for value in identity[1:]):
        raise EvidenceError("placeholder_host_identity")
    if mapped["supervisor"]["status"] == "passed" and host["supervisor_present"] is not True:
        raise EvidenceError("supervisor_presence_mismatch")
    complete = len(passed) == len(PHASES)
    if complete and host["supervisor_present"] is not True:
        raise EvidenceError("supervisor_presence_mismatch")
    return {
        "valid": True,
        "testserver_acceptance_complete": complete,
        "container_deploy_ready": False,
        "passed_phases": passed,
        "blocked_phases": blocked,
        "not_run_phases": not_run,
    }


def load(path: Path) -> tuple[dict, bytes]:
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise EvidenceError("invalid_input_file")
    data = path.read_bytes()
    if len(data) > MAX_BYTES or any(marker in data for marker in PRIVATE_MARKERS):
        raise EvidenceError("unsafe_input")
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("invalid_json") from exc
    if not isinstance(document, dict):
        raise EvidenceError("invalid_document")
    return document, data


def verify_file(path: Path, expected_archive: str, expected_manifest: str) -> dict:
    document, _ = load(path)
    result = validate_document(document, expected_archive, expected_manifest)
    canonical = (json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")
    result["result_sha256"] = digest(canonical)
    return result


def _defaults(phase_id: str) -> dict:
    hashes = {
        "data_digest_before", "data_digest_after", "profiles_digest_before",
        "profiles_digest_after", "old_image_sha256", "new_image_sha256",
        "image_sha256", "api_image_sha256", "worker_image_sha256",
        "restored_image_sha256", "backup_sha256", "source_digest", "restored_digest",
        "source_profiles_digest", "restored_profiles_digest",
    }
    integers = {"native_units", "native_markers", "native_processes", "slicer_containers", "unauthenticated_status", "authenticated_status"}
    result = {}
    for key in PHASE_CHECKS[phase_id]:
        result[key] = "0" * 64 if key in hashes else (0 if key in integers else False)
    return result


def write_template(
    path: Path,
    archive_sha256: str,
    manifest_sha256: str,
    host_fingerprint_sha256: str,
    os_id: str,
    os_version: str,
    architecture: str,
    supervisor_present: bool,
) -> dict:
    archive_sha256 = _hash(archive_sha256, "invalid_expected_archive")
    manifest_sha256 = _hash(manifest_sha256, "invalid_expected_manifest")
    host = {
        "host_fingerprint_sha256": _hash(host_fingerprint_sha256, "invalid_host_fingerprint"),
        "os_id": _word(os_id, "invalid_os_id"),
        "os_version": _word(os_version, "invalid_os_version"),
        "architecture": _word(architecture, "invalid_architecture"),
        "supervisor_present": _bool(supervisor_present, "invalid_supervisor_presence"),
    }
    identity = (host["host_fingerprint_sha256"], host["os_id"], host["os_version"], host["architecture"])
    if identity[0] == "0" * 64 or any(value == "unknown" for value in identity[1:]):
        raise EvidenceError("template_host_identity_required")
    path = Path(path).absolute()
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise EvidenceError("template_target_unavailable")
    run_sha256 = digest(os.urandom(32))
    package = {"archive_sha256": archive_sha256, "manifest_sha256": manifest_sha256, "verified": True}
    phases = []
    previous_evidence_sha256 = run_sha256
    for phase_id in PHASES:
        checks = _defaults(phase_id)
        evidence_sha256 = phase_digest(
            run_sha256,
            package,
            host,
            previous_evidence_sha256,
            phase_id,
            "not_run",
            checks,
        )
        phases.append({
            "id": phase_id,
            "status": "not_run",
            "previous_evidence_sha256": previous_evidence_sha256,
            "evidence_sha256": evidence_sha256,
            "checks": checks,
        })
        previous_evidence_sha256 = evidence_sha256
    document = {
        "schema": SCHEMA,
        "run_sha256": run_sha256,
        "package": package,
        "host": host,
        "phases": phases,
        "container_deploy_ready": False,
    }
    data = (json.dumps(document, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != data:
        raise EvidenceError("template_readback_mismatch")
    return {"template_created": True, "path": str(path), "sha256": digest(data), "container_deploy_ready": False}


def load_checks(path: Path) -> dict:
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise EvidenceError("invalid_checks_file")
    data = path.read_bytes()
    if len(data) > MAX_BYTES or any(marker in data for marker in PRIVATE_MARKERS):
        raise EvidenceError("unsafe_checks")
    try:
        checks = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("invalid_checks_json") from exc
    if not isinstance(checks, dict):
        raise EvidenceError("invalid_checks_json")
    _scan_keys(checks)
    return checks


def advance_phase(
    source: Path,
    output: Path,
    phase_id: str,
    status: str,
    checks: dict,
    expected_archive: str,
    expected_manifest: str,
) -> dict:
    document, source_data = load(source)
    validate_document(document, expected_archive, expected_manifest)
    if phase_id not in PHASE_CHECKS:
        raise EvidenceError("invalid_advance_phase")
    if status not in {"passed", "blocked"}:
        raise EvidenceError("invalid_advance_status")
    phases = document["phases"]
    index = PHASES.index(phase_id)
    phase = phases[index]
    if phase["status"] != "not_run" or any(
        previous["status"] != "passed" for previous in phases[:index]
    ):
        raise EvidenceError("phase_not_next:" + phase_id)
    _scan_keys(checks)
    _validate_checks(phase_id, checks, status == "passed")
    phase["status"] = status
    phase["checks"] = checks
    previous_evidence_sha256 = (
        document["run_sha256"]
        if index == 0
        else phases[index - 1]["evidence_sha256"]
    )
    for chained_phase in phases[index:]:
        chained_phase["previous_evidence_sha256"] = previous_evidence_sha256
        chained_phase["evidence_sha256"] = phase_digest(
            document["run_sha256"],
            document["package"],
            document["host"],
            previous_evidence_sha256,
            chained_phase["id"],
            chained_phase["status"],
            chained_phase["checks"],
        )
        previous_evidence_sha256 = chained_phase["evidence_sha256"]
    verification = validate_document(document, expected_archive, expected_manifest)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise EvidenceError("advance_target_unavailable")
    data = (json.dumps(document, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    with output.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if output.read_bytes() != data or Path(source).absolute().read_bytes() != source_data:
        output.unlink(missing_ok=True)
        raise EvidenceError("advance_readback_mismatch")
    return {
        "phase_advanced": phase_id,
        "status": status,
        "path": str(output),
        "sha256": digest(data),
        "testserver_acceptance_complete": verification["testserver_acceptance_complete"],
        "container_deploy_ready": False,
    }

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path)
    group.add_argument("--write-template", type=Path)
    group.add_argument("--advance-input", type=Path)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--host-fingerprint-sha256")
    parser.add_argument("--os-id")
    parser.add_argument("--os-version")
    parser.add_argument("--architecture")
    parser.add_argument("--supervisor-present", choices=("true", "false"))
    parser.add_argument("--write-output", type=Path)
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument("--status", choices=("passed", "blocked"))
    parser.add_argument("--checks-json", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.write_template is not None:
            required = (
                args.host_fingerprint_sha256,
                args.os_id,
                args.os_version,
                args.architecture,
                args.supervisor_present,
            )
            if any(value is None for value in required):
                raise EvidenceError("template_host_identity_required")
            result = write_template(
                args.write_template,
                args.expected_archive_sha256,
                args.expected_manifest_sha256,
                args.host_fingerprint_sha256,
                args.os_id,
                args.os_version,
                args.architecture,
                args.supervisor_present == "true",
            )
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.advance_input is not None:
            required = (args.write_output, args.phase, args.status, args.checks_json)
            if any(value is None for value in required):
                raise EvidenceError("advance_arguments_required")
            result = advance_phase(
                args.advance_input,
                args.write_output,
                args.phase,
                args.status,
                load_checks(args.checks_json),
                args.expected_archive_sha256,
                args.expected_manifest_sha256,
            )
            print(json.dumps(result, sort_keys=True))
            return 0
        if any(value is not None for value in (args.write_output, args.phase, args.status, args.checks_json)):
            raise EvidenceError("advance_arguments_without_advance")
        result = verify_file(args.input, args.expected_archive_sha256, args.expected_manifest_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["testserver_acceptance_complete"] else 2
    except (EvidenceError, OSError) as exc:
        code = str(exc) if isinstance(exc, EvidenceError) else type(exc).__name__
        parser.exit(1, "Evidence rejected: " + code + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
