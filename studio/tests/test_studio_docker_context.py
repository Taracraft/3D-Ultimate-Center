"""Offline Docker packaging checks; no engine, daemon or native worker execution."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]

def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "Slicer-Server" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

prep = module("studio_docker_prepare", "prepare_context.py")
check = module("studio_docker_check", "container_check.py")

def source(root):
    def put(name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    host, dependencies = {}, {}
    for name in prep.HOST_FILES:
        data = ("synthetic:" + name + "\n").encode()
        put(prep.HOST + "/" + name, data)
        (dependencies if name == "job_control.py" else host)[name] = prep.digest(data)
    for name in prep.COMPONENT_FILES:
        data = ("synthetic-component:" + name + "\n").encode()
        put(prep.COMPONENT + "/" + name, data)
        dependencies[name] = prep.digest(data)
    for name, rows in (("SHA256SUMS", host), ("DEPENDENCY-SHA256SUMS", dependencies)):
        put(prep.HOST + "/" + name, "".join(value + "  " + key + "\n" for key, value in rows.items()).encode())
    put("packages/ultimate-slicer-server/release.json", b'{"version":"0.1.0-test","api_protocol":2}\n')
    for name in prep.SUPPORT_FILES:
        put("Slicer-Server/" + name, ("fixture:" + name + "\n").encode())
    for name in (*prep.LICENSE_FILES, "PAYLOAD_PROVENANCE.json", prep.PROFILE_SOURCE_FILE):
        put("Slicer-Server/" + name, (ROOT / "Slicer-Server" / name).read_bytes())
    provenance_path = root / "Slicer-Server/PAYLOAD_PROVENANCE.json"
    provenance = json.loads(provenance_path.read_text())
    for row in provenance["payload_files"]:
        row["sha256"] = prep.digest((root / row["source"]).read_bytes())
    provenance_path.write_text(json.dumps(provenance))
    return root

def test_real_source_closure_is_read_only_and_not_a_release():
    payload, manifest = prep.collect(ROOT)
    assert len(payload) == 39
    assert len([p for p in payload if p.startswith("payload/")]) == 20
    assert manifest["container_deploy_ready"] is False
    assert manifest["engine_included"] is False
    assert manifest["sources_are_not_relicensed"] is True
    assert not any("systemd" in p or "config.json" in p for p in payload)

def test_context_is_complete_deterministic_and_has_no_private_neighbors(tmp_path):
    root = source(tmp_path / "source")
    (root / prep.HOST / "config.json").write_text('{"not_for_distribution":true}')
    (root / prep.COMPONENT / "credentials.json").write_text('{"not_for_distribution":true}')
    first, second = tmp_path / "first", tmp_path / "second"
    prep.prepare(root, first)
    prep.prepare(root, second)
    assert {p.relative_to(first): p.read_bytes() for p in first.rglob("*") if p.is_file()} == {
        p.relative_to(second): p.read_bytes() for p in second.rglob("*") if p.is_file()}
    result = check.verify(first)
    assert result["source_integrity"] == "verified"
    assert result["worker_started"] is False and result["installation_performed"] is False

@pytest.mark.parametrize("name", ["server.py", "job_control.py", "dispatch-job.sh"])
def test_changed_native_source_is_rejected_before_output(tmp_path, name):
    root = source(tmp_path / "source")
    (root / prep.HOST / name).write_bytes(b"unreviewed")
    with pytest.raises(prep.ContextError, match="source_digest_mismatch"):
        prep.prepare(root, tmp_path / "context")
    assert not (tmp_path / "context").exists()

def test_component_authority_has_no_neighbor_fallback(tmp_path):
    root = source(tmp_path / "source")
    name = prep.COMPONENT_FILES[0]
    data = (root / prep.COMPONENT / name).read_bytes()
    (root / prep.COMPONENT / name).unlink()
    (root / prep.HOST / name).write_bytes(data)
    with pytest.raises(FileNotFoundError):
        prep.collect(root)

def test_existing_target_is_not_modified(tmp_path):
    root = source(tmp_path / "source")
    target = tmp_path / "context"
    target.mkdir()
    (target / "keep").write_bytes(b"existing")
    with pytest.raises(prep.ContextError, match="output_already_exists"):
        prep.prepare(root, target)
    assert list(target.iterdir()) == [target / "keep"]
    assert (target / "keep").read_bytes() == b"existing"

def test_generated_context_cannot_live_in_source(tmp_path):
    root = source(tmp_path / "source")
    with pytest.raises(prep.ContextError, match="output_must_be_outside_source"):
        prep.prepare(root, root / "generated")
    assert not (root / "generated").exists()

@pytest.mark.parametrize("kind", ["changed", "extra", "missing", "duplicate", "traversal", "release_flag"])
def test_checker_rejects_incomplete_or_modified_context(tmp_path, kind):
    root = source(tmp_path / "source")
    output = tmp_path / "context"
    prep.prepare(root, output)
    if kind == "changed":
        (output / "payload/server.py").write_bytes(b"changed")
    elif kind == "extra":
        (output / "config.json").write_text("{}")
    elif kind == "missing":
        (output / "payload/server.py").unlink()
    else:
        path = output / "context-manifest.json"
        manifest = json.loads(path.read_text())
        if kind == "duplicate":
            manifest["files"].append(manifest["files"][0])
        elif kind == "traversal":
            manifest["files"][0]["path"] = "../outside"
        else:
            manifest["container_deploy_ready"] = True
        path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        check.verify(output)

def test_checksum_manifest_rejects_duplicate_entries():
    line = "a" * 64 + "  file.py\n"
    with pytest.raises(prep.ContextError, match="invalid_source_manifest"):
        prep.checksum_map((line + line).encode())

def test_preview_cannot_start_a_worker():
    with pytest.raises(SystemExit) as error:
        check.main(["serve"])
    assert error.value.code == 2

def test_compose_preflight_has_no_runtime_access():
    doc = json.loads((ROOT / "Slicer-Server/compose.preview.yaml").read_text())
    service = doc["services"]["preflight"]
    assert service["command"] == ["check"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True and service["user"] == "65532:65532"
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert service["pull_policy"] == "never"
    assert not any(k in service for k in ("ports", "volumes", "privileged", "devices"))

@pytest.mark.skipif(sys.platform == "win32", reason="Windows symlinks require extra privileges")
def test_linked_component_source_is_rejected(tmp_path):
    root = source(tmp_path / "source")
    path = root / prep.COMPONENT / prep.COMPONENT_FILES[0]
    outside = tmp_path / "outside"
    path.rename(outside)
    path.symlink_to(outside)
    with pytest.raises(prep.ContextError, match="linked_source"):
        prep.collect(root)


runtime = module("studio_container_runtime", "container_runtime.py")

def isolated_state():
    return {"uids": [65532] * 4,
            "capabilities": {key: 0 for key in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")},
            "no_new_privileges": 1, "seccomp": 2, "interfaces": ["lo"],
            "net_self": "net:[2]", "net_anchor": "net:[1]",
            "pid_self": "pid:[3]", "pid_anchor": "pid:[3]"}

@pytest.mark.parametrize("field,value,error", [
    ("uids", [65532, 0, 65532, 65532], "nonroot"),
    ("uids", [], "nonroot"),
    ("capabilities", {"CapEff": 0}, "zero_capabilities"),
    ("no_new_privileges", 0, "kernel_protection"),
    ("seccomp", 0, "kernel_protection"),
    ("interfaces", ["eth0", "lo"], "network_none"),
    ("interfaces", [], "network_none"),
    ("net_self", "net:[1]", "separate_anchor_network"),
    ("net_anchor", "", "separate_anchor_network"),
    ("pid_anchor", "pid:[4]", "shared_pid_visibility"),
])
def test_runtime_rejects_weakened_kernel_contract(field, value, error):
    state = isolated_state()
    state[field] = value
    with pytest.raises(runtime.IsolationError, match=error):
        runtime.validate(state)

@pytest.mark.parametrize("capability", ["CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"])
def test_runtime_rejects_each_capability_set(capability):
    state = isolated_state()
    state["capabilities"][capability] = 1
    with pytest.raises(runtime.IsolationError, match="zero_capabilities"):
        runtime.validate(state)

def test_runtime_accepts_required_kernel_evidence():
    state = isolated_state()
    assert runtime.validate(state) == state

def test_runtime_missing_kernel_evidence_fails_closed(monkeypatch):
    def missing():
        raise FileNotFoundError("not Linux")
    monkeypatch.setattr(runtime, "observe", missing)
    with pytest.raises(runtime.IsolationError, match="kernel_evidence_unavailable"):
        runtime.require_isolation()

def test_supervisor_never_starts_before_isolation_or_after_stop(monkeypatch):
    import threading
    stop = threading.Event()
    monkeypatch.setattr(runtime, "require_isolation", lambda: (_ for _ in ()).throw(runtime.IsolationError("blocked")))
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: pytest.fail("must not spawn"))
    with pytest.raises(runtime.IsolationError):
        runtime.supervise(["unused"], stop=stop, stdout=None, stderr=None)
    monkeypatch.setattr(runtime, "require_isolation", lambda: isolated_state())
    stop.set()
    assert runtime.supervise(["unused"], stop=stop, stdout=None, stderr=None)["status"] == "stopped_before_start"

def test_supervisor_forwards_stop_once_and_waits(monkeypatch):
    import threading
    stop = threading.Event()
    signals = []
    class Child:
        calls = 0
        def poll(self):
            self.calls += 1
            stop.set()
            return 0 if self.calls == 4 else None
        def send_signal(self, sig):
            signals.append(sig)
    monkeypatch.setattr(runtime, "require_isolation", lambda: isolated_state())
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: Child())
    monkeypatch.setattr(runtime.time, "sleep", lambda _: None)
    assert runtime.supervise(["unused"], stop=stop, stdout=None, stderr=None)["status"] == "stopped"
    assert signals == [runtime.signal.SIGTERM]

def test_supervisor_failure_requires_recovery(monkeypatch):
    import threading
    class Child:
        def poll(self):
            return 7
    monkeypatch.setattr(runtime, "require_isolation", lambda: isolated_state())
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: Child())
    with pytest.raises(runtime.RecoveryRequired, match="supervisor_failed:7"):
        runtime.supervise(["unused"], stop=threading.Event(), stdout=None, stderr=None)

def test_supervisor_timeout_retains_owned_child_without_force_kill(monkeypatch):
    import threading
    stop = threading.Event()
    signals = []
    class Child:
        def poll(self):
            stop.set()
            return None
        def send_signal(self, sig):
            signals.append(sig)
    child = Child()
    monkeypatch.setattr(runtime, "require_isolation", lambda: isolated_state())
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: child)
    clock = iter([0, 0, 10])
    monkeypatch.setattr(runtime.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(runtime.time, "sleep", lambda _: None)
    with pytest.raises(runtime.RecoveryRequired, match="supervisor_shutdown_timeout") as error:
        runtime.supervise(["unused"], stop=stop, stdout=None, stderr=None, shutdown_timeout=1)
    assert error.value.supervisor is child
    assert signals == [runtime.signal.SIGTERM]


@pytest.mark.parametrize("token,allowed", [(b"G", True), (b"S", False), (b"X", None), (b"", None)])
def test_start_permit_protocol_and_descriptor_cleanup(monkeypatch, token, allowed):
    import os
    ready_r, ready_w = os.pipe()
    permit_r, permit_w = os.pipe()
    monkeypatch.setenv("STUDIO_READY_FD", str(ready_w))
    monkeypatch.setenv("STUDIO_PERMIT_FD", str(permit_r))
    monkeypatch.setattr(runtime.select, "select", lambda *args: ([permit_r], [], []))
    if token:
        os.write(permit_w, token)
    os.close(permit_w)
    try:
        if allowed is None:
            with pytest.raises(runtime.RecoveryRequired, match="invalid_start_permission"):
                runtime.start_permit()
        else:
            assert runtime.start_permit() is allowed
        assert os.read(ready_r, 1) == b"R"
        for fd in (ready_w, permit_r):
            with pytest.raises(OSError):
                os.fstat(fd)
        assert "STUDIO_READY_FD" not in os.environ
        assert "STUDIO_PERMIT_FD" not in os.environ
    finally:
        os.close(ready_r)

def test_start_permission_timeout_closes_descriptors(monkeypatch):
    import os
    ready_r, ready_w = os.pipe()
    permit_r, permit_w = os.pipe()
    monkeypatch.setenv("STUDIO_READY_FD", str(ready_w))
    monkeypatch.setenv("STUDIO_PERMIT_FD", str(permit_r))
    monkeypatch.setattr(runtime.select, "select", lambda *args: ([], [], []))
    try:
        with pytest.raises(runtime.RecoveryRequired, match="start_permission_timeout"):
            runtime.start_permit()
        for fd in (ready_w, permit_r):
            with pytest.raises(OSError):
                os.fstat(fd)
    finally:
        os.close(ready_r)
        os.close(permit_w)

@pytest.mark.parametrize("argument", ["startup_timeout", "shutdown_timeout"])
def test_supervisor_invalid_deadline_cannot_spawn(monkeypatch, argument):
    import threading
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: pytest.fail("must not spawn"))
    with pytest.raises(ValueError, match="timeouts_must_be_positive"):
        runtime.supervise(["unused"], stop=threading.Event(), stdout=None, stderr=None, **{argument: 0})


service = module("studio_container_service", "container_service.py")

@pytest.mark.parametrize("result", [
    {}, None, {"status": "blocked"}, {"status": "cancelling"},
    {"status": "completed", "requires_recovery": True},
])
def test_service_blocks_unknown_or_recovery_results(result):
    assert service.terminal_requires_recovery(result)

@pytest.mark.parametrize("state", ["idle", "completed", "failed", "cancelled"])
def test_service_accepts_only_known_terminal_results(state):
    assert not service.terminal_requires_recovery({"status": state})

def test_service_api_uses_file_secret_and_requires_tls(tmp_path):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    service.initialize_profiles(profiles, seed=ROOT / prep.HOST / "profiles/printers")
    data = tmp_path / "data"
    data.mkdir()
    service.initialize_data(data)
    token = tmp_path / "token"
    token.write_text("s" * 48 + "\n")
    if sys.platform != "win32":
        token.chmod(0o600)
    cert, key = tmp_path / "server.crt", tmp_path / "server.key"
    with pytest.raises(ValueError, match="tls_files_required"):
        service.api_configuration(data, token, cert, key, profiles)
    cert.write_text("fixture certificate")
    key.write_text("fixture key")
    if sys.platform != "win32":
        key.chmod(0o600)
    value = service.api_configuration(data, token, cert, key, profiles)
    assert value["token"] == "s" * 48
    assert value["host"] == "0.0.0.0" and value["tls_certfile"] == str(cert)
    token.write_text("short")
    with pytest.raises(ValueError, match="invalid_api_secret"):
        service.api_configuration(data, token, cert, key, profiles)

def test_data_initializer_is_idempotent_and_preserves_runtime_contents(tmp_path):
    base = tmp_path / "data"
    base.mkdir()
    assert service.initialize_data(base) == {"initialized": True, "state": "ready", "dispatch_blocked": False}
    upload = base / "data/uploads/keep.3mf"
    upload.write_bytes(b"user-data")
    receipt = (base / "DATA_STATE.json").read_bytes()
    assert service.initialize_data(base) == {"initialized": False, "state": "ready", "dispatch_blocked": False}
    assert upload.read_bytes() == b"user-data"
    assert (base / "DATA_STATE.json").read_bytes() == receipt
    assert service.persistent_data(base) == base


@pytest.mark.parametrize("name", ["foreign.txt", "data", "run"])
def test_data_initializer_never_adopts_foreign_or_partial_trees(tmp_path, name):
    base = tmp_path / "data"
    base.mkdir()
    path = base / name
    path.mkdir() if "." not in name else path.write_text("keep")
    with pytest.raises(ValueError, match="data_foreign_contents"):
        service.initialize_data(base)
    assert path.exists()
    assert not (base / "DATA_STATE.json").exists()


@pytest.mark.parametrize("mutation", ["preparing", "missing", "extra", "permissions"])
def test_data_consumers_fail_closed_on_incomplete_or_changed_tree(tmp_path, mutation):
    base = tmp_path / "data"
    base.mkdir()
    service.initialize_data(base)
    if mutation == "preparing":
        state = json.loads((base / "DATA_STATE.json").read_text())
        state["state"] = "preparing"
        (base / "DATA_STATE.json").write_text(json.dumps(state))
    elif mutation == "missing":
        (base / "data/uploads").rmdir()
    elif mutation == "extra":
        (base / "unexpected").mkdir()
    elif sys.platform != "win32":
        (base / "data/jobs").chmod(0o770)
    else:
        pytest.skip("POSIX permission contract")
    with pytest.raises(ValueError):
        service.persistent_data(base)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX link and permission contract")
def test_data_and_credentials_reject_links_hardlinks_and_exposed_secrets(tmp_path):
    base = tmp_path / "data"
    base.mkdir()
    service.initialize_data(base)
    original = base / "data/uploads"
    moved = base / "data/uploads.saved"
    original.rename(moved)
    original.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError, match="data_link_rejected"):
        service.persistent_data(base)

    token = tmp_path / "token"
    token.write_text("s" * 48)
    token.chmod(0o644)
    with pytest.raises(ValueError, match="api_secret_permissions_rejected"):
        service._regular_bytes(token, service.SECRET_BYTES, "api_secret", private=True)
    token.chmod(0o600)
    alias = tmp_path / "token-alias"
    alias.symlink_to(token)
    with pytest.raises(ValueError, match="api_secret_link_rejected"):
        service._regular_bytes(alias, service.SECRET_BYTES, "api_secret", private=True)
    hard = tmp_path / "token-hard"
    import os
    os.link(token, hard)
    with pytest.raises(ValueError, match="api_secret_regular_bounded_file_required"):
        service._regular_bytes(token, service.SECRET_BYTES, "api_secret", private=True)


def test_credentials_are_bounded_and_token_newline_is_strict(tmp_path):
    data = tmp_path / "data"
    profiles = tmp_path / "profiles"
    data.mkdir()
    profiles.mkdir()
    service.initialize_data(data)
    service.initialize_profiles(profiles, seed=ROOT / prep.HOST / "profiles/printers")
    token, cert, key = [tmp_path / name for name in ("token", "cert", "key")]
    token.write_text("s" * 48 + "\n")
    cert.write_text("fixture certificate")
    key.write_text("fixture key")
    if sys.platform != "win32":
        token.chmod(0o600)
        key.chmod(0o600)
        cert.chmod(0o644)
    assert service.api_configuration(data, token, cert, key, profiles)["token"] == "s" * 48
    token.write_text("s" * 48 + "\n\n")
    with pytest.raises(ValueError, match="invalid_api_secret"):
        service.api_configuration(data, token, cert, key, profiles)
    token.write_bytes(b"s" * (service.SECRET_BYTES + 1))
    with pytest.raises(ValueError, match="api_secret_regular_bounded_file_required"):
        service.api_configuration(data, token, cert, key, profiles)

def test_service_compose_separates_networks_and_preserves_stop_order():
    doc = json.loads((ROOT / "Slicer-Server/compose.candidate.yaml").read_text())
    api, worker = doc["services"]["api"], doc["services"]["worker"]
    data_init = doc["services"]["data-init"]
    maintenance_clear = doc["services"]["maintenance-clear"]
    assert api["init"] is True
    assert data_init["command"] == ["init-data"] and data_init["network_mode"] == "none"
    assert data_init["user"] == "65532:65532" and data_init["read_only"] is True
    assert data_init["volumes"][0]["read_only"] is False
    assert data_init["volumes"][0]["bind"]["create_host_path"] is False
    assert maintenance_clear["profiles"] == ["maintenance"]
    assert maintenance_clear["command"] == ["maintenance-end", "--request-id",
                                             "${SLICER_BOOTSTRAP_REQUEST_ID:-}"]
    assert maintenance_clear["network_mode"] == "none"
    assert maintenance_clear["user"] == "65532:65532" and maintenance_clear["read_only"] is True
    assert maintenance_clear["volumes"] == data_init["volumes"]
    assert api["depends_on"]["data-init"]["condition"] == "service_completed_successfully"
    assert worker["network_mode"] == "none" and worker["pid"] == "service:api"
    assert worker["depends_on"]["api"]["restart"] is True
    for entry in (api, worker):
        assert entry["restart"] == "no"
        assert entry["read_only"] and entry["cap_drop"] == ["ALL"]
        assert entry["stop_grace_period"] == "60s"
        assert all(m["bind"]["create_host_path"] is False for m in entry["volumes"])
    assert not any(m["target"].startswith("/run/secrets") for m in worker["volumes"])


def test_container_exec_cannot_run_without_kernel_evidence(monkeypatch):
    monkeypatch.setattr(runtime, "require_isolation", lambda: (_ for _ in ()).throw(runtime.IsolationError("blocked")))
    monkeypatch.setattr(runtime.os, "execvp", lambda *args: pytest.fail("must not execute"))
    with pytest.raises(runtime.IsolationError):
        runtime.exec_isolated(["synthetic-engine"])

def test_container_exec_preserves_argument_boundaries(monkeypatch):
    calls = []
    monkeypatch.setattr(runtime, "require_isolation", lambda: isolated_state())
    monkeypatch.setattr(runtime.os, "execvp", lambda executable, argv: calls.append((executable, argv)))
    args = ["synthetic-engine", "name with spaces", "$(no-shell)"]
    runtime.exec_isolated(args)
    assert calls == [("synthetic-engine", args)]
