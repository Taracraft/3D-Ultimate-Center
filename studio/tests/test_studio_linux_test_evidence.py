"""Synthetic checks for the Linux test-server evidence contract."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "Slicer-Server" / "linux_test_evidence.py"
SPEC = importlib.util.spec_from_file_location("studio_linux_test_evidence", MODULE_PATH)
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
E = "e" * 64


def passed_checks(phase_id):
    values = evidence._defaults(phase_id)
    for key, value in tuple(values.items()):
        if type(value) is bool:
            values[key] = True
    if phase_id == "clean_host":
        values.update(inventory_complete=True, clean=True)
    if phase_id == "compose":
        values.update(image_sha256=A)
    if phase_id == "runtime":
        values.update(api_image_sha256=A, worker_image_sha256=A)
    if phase_id == "tls":
        values.update(
            certificate_verified=True,
            hostname_verified=True,
            unauthenticated_status=401,
            authenticated_status=200,
            secret_in_argv_or_env=False,
            private_key_exported=False,
        )
    if phase_id == "persistence":
        values.update(data_digest_before=C, data_digest_after=C, profiles_digest_before=D, profiles_digest_after=D)
    if phase_id == "upgrade":
        values.update(
            old_image_sha256=A, new_image_sha256=B,
            data_digest_before=C, data_digest_after=C,
            profiles_digest_before=D, profiles_digest_after=D,
        )
    if phase_id == "rollback":
        values.update(
            restored_image_sha256=A,
            data_digest_before=C, data_digest_after=C,
            profiles_digest_before=D, profiles_digest_after=D,
        )
    if phase_id == "backup_restore":
        values.update(
            backup_sha256=E, source_digest=C, restored_digest=C,
            source_profiles_digest=D, restored_profiles_digest=D,
        )
    return values


def rehash(value):
    previous_evidence_sha256 = value["run_sha256"]
    for phase in value["phases"]:
        phase["previous_evidence_sha256"] = previous_evidence_sha256
        phase["evidence_sha256"] = evidence.phase_digest(
            value["run_sha256"],
            value["package"],
            value["host"],
            previous_evidence_sha256,
            phase["id"],
            phase["status"],
            phase["checks"],
        )
        previous_evidence_sha256 = phase["evidence_sha256"]
    return value


def document(status_overrides=None, run_sha256=D, host_fingerprint=C):
    status_overrides = status_overrides or {}
    package = {"archive_sha256": A, "manifest_sha256": B, "verified": True}
    host = {
        "host_fingerprint_sha256": host_fingerprint,
        "os_id": "debian",
        "os_version": "13",
        "architecture": "x86_64",
        "supervisor_present": True,
    }
    phases = []
    for phase_id in evidence.PHASES:
        checks = passed_checks(phase_id)
        status = status_overrides.get(phase_id, "passed")
        phases.append(
            {
                "id": phase_id,
                "status": status,
                "evidence_sha256": A,
                "checks": checks,
            }
        )
    return rehash(
        {
            "schema": evidence.SCHEMA,
            "run_sha256": run_sha256,
            "package": package,
            "host": host,
            "phases": phases,
            "container_deploy_ready": False,
        }
    )


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_complete_bundle_is_valid_but_never_sets_release_ready(tmp_path):
    result = evidence.verify_file(write(tmp_path / "result.json", document()), A, B)
    assert result["valid"] is True
    assert result["testserver_acceptance_complete"] is True
    assert result["container_deploy_ready"] is False
    assert result["passed_phases"] == list(evidence.PHASES)


def test_blocked_phase_is_valid_incomplete_evidence(tmp_path):
    value = document({
        "upgrade": "blocked",
        "rollback": "not_run",
        "backup_restore": "not_run",
        "supervisor": "not_run",
    })
    value["phases"][evidence.PHASES.index("upgrade")]["checks"]["ready_paused"] = False
    rehash(value)
    result = evidence.verify_file(write(tmp_path / "result.json", value), A, B)
    assert result["testserver_acceptance_complete"] is False
    assert result["blocked_phases"] == ["upgrade"]
    assert result["not_run_phases"] == ["rollback", "backup_restore", "supervisor"]


@pytest.mark.parametrize(
    "mutator,error",
    [
        (lambda value: value["package"].__setitem__("archive_sha256", D), "archive_digest_mismatch"),
        (lambda value: value.__setitem__("container_deploy_ready", True), "release_flag_rejected"),
        (lambda value: value["phases"][0].__setitem__("evidence_sha256", D), "phase_digest_mismatch"),
        (lambda value: value["phases"][0]["checks"].__setitem__("api_token", "redacted"), "forbidden_field"),
        (lambda value: value["phases"][1]["checks"].__setitem__("native_units", True), "invalid_inventory_count"),
        (lambda value: value["phases"][4]["checks"].__setitem__("secret_in_argv_or_env", True), "passed_phase_contract_failed:tls"),
        (lambda value: value["phases"][5]["checks"].__setitem__("data_digest_after", D), "passed_phase_contract_failed:persistence"),
    ],
)
def test_fail_closed_contract_rejections(tmp_path, mutator, error):
    value = document()
    mutator(value)
    if not error.startswith("phase_digest_mismatch"):
        rehash(value)
    with pytest.raises(evidence.EvidenceError, match=error):
        evidence.verify_file(write(tmp_path / "result.json", value), A, B)


def test_duplicate_json_and_private_key_are_rejected(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema":1,"schema":1}', encoding="utf-8")
    with pytest.raises(evidence.EvidenceError, match="duplicate_json_key"):
        evidence.load(duplicate)
    private = tmp_path / "private.json"
    private.write_bytes(b'{"x":"-----BEGIN PRIVATE KEY-----"}')
    with pytest.raises(evidence.EvidenceError, match="unsafe_input"):
        evidence.load(private)


def test_template_is_new_only_hash_bound_and_incomplete(tmp_path):
    target = tmp_path / "evidence.json"
    created = evidence.write_template(target, A, B, C, "debian", "13", "x86_64", True)
    assert created["template_created"] is True
    result = evidence.verify_file(target, A, B)
    assert result["testserver_acceptance_complete"] is False
    assert result["not_run_phases"] == list(evidence.PHASES)
    with pytest.raises(evidence.EvidenceError, match="template_target_unavailable"):
        evidence.write_template(target, A, B, C, "debian", "13", "x86_64", True)


def test_phase_order_and_exact_set_are_required(tmp_path):
    value = document()
    value["phases"][0], value["phases"][1] = value["phases"][1], value["phases"][0]
    with pytest.raises(evidence.EvidenceError, match="phase_order_mismatch"):
        evidence.verify_file(write(tmp_path / "result.json", value), A, B)

def test_status_change_requires_new_phase_digest(tmp_path):
    statuses = {phase_id: "not_run" for phase_id in evidence.PHASES[6:]}
    statuses["upgrade"] = "blocked"
    value = document(statuses)
    phase = value["phases"][evidence.PHASES.index("upgrade")]
    phase["status"] = "passed"
    with pytest.raises(evidence.EvidenceError, match="phase_digest_mismatch:upgrade"):
        evidence.verify_file(write(tmp_path / "result.json", value), A, B)


def test_passed_phases_must_form_a_prefix(tmp_path):
    statuses = {phase_id: "not_run" for phase_id in evidence.PHASES[2:]}
    statuses["clean_host"] = "blocked"
    statuses["runtime"] = "passed"
    value = document(statuses)
    with pytest.raises(evidence.EvidenceError, match="phase_sequence_invalid:runtime"):
        evidence.verify_file(write(tmp_path / "result.json", value), A, B)


def test_complete_bundle_rejects_placeholder_host_identity(tmp_path):
    value = document()
    value["host"].update(
        host_fingerprint_sha256="0" * 64,
        os_id="unknown",
        os_version="unknown",
        architecture="unknown",
    )
    rehash(value)
    with pytest.raises(evidence.EvidenceError, match="placeholder_host_identity"):
        evidence.verify_file(write(tmp_path / "result.json", value), A, B)


def test_supervisor_phase_requires_reported_supervisor(tmp_path):
    value = document()
    value["host"]["supervisor_present"] = False
    rehash(value)
    with pytest.raises(evidence.EvidenceError, match="supervisor_presence_mismatch"):
        evidence.verify_file(write(tmp_path / "result.json", value), A, B)



def test_phase_evidence_is_bound_to_run_package_and_host(tmp_path):
    first = document(run_sha256=D, host_fingerprint=C)
    second = document(run_sha256="e" * 64, host_fingerprint="f" * 64)
    first["phases"][5:] = copy.deepcopy(second["phases"][5:])
    with pytest.raises(evidence.EvidenceError, match="phase_chain_mismatch:persistence"):
        evidence.verify_file(write(tmp_path / "mixed.json", first), A, B)


def test_template_requires_concrete_host_identity(tmp_path):
    with pytest.raises(evidence.EvidenceError, match="template_host_identity_required"):
        evidence.write_template(
            tmp_path / "evidence.json",
            A,
            B,
            "0" * 64,
            "unknown",
            "unknown",
            "unknown",
            False,
        )


def test_complete_bundle_rejects_cross_phase_state_splice(tmp_path):
    value = document()
    phases = {phase["id"]: phase for phase in value["phases"]}
    phases["persistence"]["checks"].update(
        data_digest_before="1" * 64,
        data_digest_after="1" * 64,
        profiles_digest_before="5" * 64,
        profiles_digest_after="5" * 64,
    )
    phases["upgrade"]["checks"].update(
        data_digest_before="2" * 64,
        data_digest_after="2" * 64,
        profiles_digest_before="6" * 64,
        profiles_digest_after="6" * 64,
    )
    phases["rollback"]["checks"].update(
        data_digest_before="3" * 64,
        data_digest_after="3" * 64,
        profiles_digest_before="7" * 64,
        profiles_digest_after="7" * 64,
    )
    phases["backup_restore"]["checks"].update(
        source_digest="4" * 64,
        restored_digest="4" * 64,
        source_profiles_digest="8" * 64,
        restored_profiles_digest="8" * 64,
    )
    rehash(value)
    with pytest.raises(
        evidence.EvidenceError,
        match="phase_continuity_mismatch:persistence_upgrade_data",
    ):
        evidence.verify_file(write(tmp_path / "state-splice.json", value), A, B)


def test_complete_bundle_rejects_image_identity_splice(tmp_path):
    value = document()
    runtime = value["phases"][evidence.PHASES.index("runtime")]
    runtime["checks"].update(
        api_image_sha256=E,
        worker_image_sha256=E,
    )
    rehash(value)
    with pytest.raises(
        evidence.EvidenceError,
        match="phase_continuity_mismatch:compose_runtime_image",
    ):
        evidence.verify_file(write(tmp_path / "image-splice.json", value), A, B)


def test_advance_phase_writes_new_hash_bound_result_and_preserves_input(tmp_path):
    source = tmp_path / "evidence-00.json"
    evidence.write_template(source, A, B, C, "debian", "13", "x86_64", True)
    source_before = source.read_bytes()
    checks = write(tmp_path / "package-checks.json", passed_checks("package"))
    output = tmp_path / "evidence-01.json"

    result = evidence.advance_phase(
        source, output, "package", "passed", evidence.load_checks(checks), A, B
    )

    assert source.read_bytes() == source_before
    assert result["phase_advanced"] == "package"
    assert result["status"] == "passed"
    assert result["container_deploy_ready"] is False
    verified = evidence.verify_file(output, A, B)
    assert verified["passed_phases"] == ["package"]
    assert verified["not_run_phases"] == list(evidence.PHASES[1:])


def test_advance_phase_rejects_skip_existing_target_and_post_block_progress(tmp_path):
    source = tmp_path / "evidence-00.json"
    evidence.write_template(source, A, B, C, "debian", "13", "x86_64", True)
    with pytest.raises(evidence.EvidenceError, match="phase_not_next:clean_host"):
        evidence.advance_phase(
            source,
            tmp_path / "skip.json",
            "clean_host",
            "passed",
            passed_checks("clean_host"),
            A,
            B,
        )

    existing = tmp_path / "existing.json"
    existing.write_text("keep", encoding="utf-8")
    with pytest.raises(evidence.EvidenceError, match="advance_target_unavailable"):
        evidence.advance_phase(
            source, existing, "package", "passed", passed_checks("package"), A, B
        )
    assert existing.read_text(encoding="utf-8") == "keep"

    blocked = tmp_path / "evidence-blocked.json"
    evidence.advance_phase(
        source, blocked, "package", "blocked", evidence._defaults("package"), A, B
    )
    with pytest.raises(evidence.EvidenceError, match="phase_not_next:clean_host"):
        evidence.advance_phase(
            blocked,
            tmp_path / "after-block.json",
            "clean_host",
            "passed",
            passed_checks("clean_host"),
            A,
            B,
        )


def test_advance_checks_reject_duplicate_keys_and_private_material(tmp_path):
    duplicate = tmp_path / "duplicate-checks.json"
    duplicate.write_text('{"sidecar_verified":true,"sidecar_verified":true}', encoding="utf-8")
    with pytest.raises(evidence.EvidenceError, match="duplicate_json_key"):
        evidence.load_checks(duplicate)

    private = tmp_path / "private-checks.json"
    private.write_bytes(b'{"note":"-----BEGIN PRIVATE KEY-----"}')
    with pytest.raises(evidence.EvidenceError, match="unsafe_checks"):
        evidence.load_checks(private)

def test_same_run_branch_phase_splice_breaks_predecessor_chain(tmp_path):
    first = document()
    second = copy.deepcopy(first)
    upgrade_index = evidence.PHASES.index("upgrade")
    second["phases"][upgrade_index]["checks"]["new_image_sha256"] = "f" * 64
    rehash(second)

    first["phases"][upgrade_index] = copy.deepcopy(second["phases"][upgrade_index])

    with pytest.raises(
        evidence.EvidenceError,
        match="phase_chain_mismatch:rollback",
    ):
        evidence.verify_file(write(tmp_path / "same-run-branch-splice.json", first), A, B)


def test_template_and_advance_chain_every_phase_to_its_predecessor(tmp_path):
    source = tmp_path / "evidence-00.json"
    evidence.write_template(source, A, B, C, "debian", "13", "x86_64", True)
    template, _ = evidence.load(source)
    previous = template["run_sha256"]
    for phase in template["phases"]:
        assert phase["previous_evidence_sha256"] == previous
        previous = phase["evidence_sha256"]

    output = tmp_path / "evidence-01.json"
    evidence.advance_phase(
        source, output, "package", "passed", passed_checks("package"), A, B
    )
    advanced, _ = evidence.load(output)
    previous = advanced["run_sha256"]
    for phase in advanced["phases"]:
        assert phase["previous_evidence_sha256"] == previous
        previous = phase["evidence_sha256"]