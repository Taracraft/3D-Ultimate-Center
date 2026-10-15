"""Authenticated installer + actual store/lifecycle/adapter; no Docker or network."""
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
def fixture(name):
    spec = importlib.util.spec_from_file_location("fixture_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
core = fixture("test_studio_restricted_installer")
runtime = fixture("test_studio_docker_host_adapter")
import package_activation as activation
import restricted_installer as installer
from installer_lifecycle import InstallerLifecycle
import docker_host_adapter as docker

spec = importlib.util.spec_from_file_location("installer_job_control",
    HERE.parent / "deploy/homeassistant/host/3d-printer-slicing-server/job_control.py")
job_control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job_control)

IDENT = "a" * 32


class CouplingTests(unittest.TestCase):
    def setUp(self):
        self.f = core.InstallerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        prepared = self.f.ready()
        first = self.f.call("activate", target=prepared)
        self.assertTrue(first["ok"], first)
        self.old = first["generation_id"]
        self.d = runtime.AdapterTests()
        self.d.setUp()
        self.addCleanup(self.d.doCleanups)
        self.config = replace(self.d.config, store=self.f.policy.store)
        self.runner = runtime.FakeRunner(self.config)
        self.runner.generation = self.old
        self.control = job_control.JobControl(self.config.data)
        self.fail_start = False
        self.fail_health = False
        self.events = []
        def boundary(argv, *, env, timeout):
            if argv[1:3] == ("container", "exec"):
                op, ident = argv[8], argv[10]
                self.events.append(op)
                callback = (self.control.begin_maintenance if op == "maintenance-begin"
                            else self.control.end_maintenance)
                return docker.Result(0, json.dumps(callback(ident)).encode(), b"")
            if argv[1:3] == ("container", "stop"):
                self.events.append("stop")
            if argv[1] == "compose":
                self.events.append("start")
                if self.fail_start:
                    raise docker.DockerAdapterError("synthetic_start_failed")
            result = self.runner(argv, env=env, timeout=timeout)
            if argv[1] == "compose" and self.fail_health:
                self.runner.healthy = False
            return result
        self.driver = docker.DockerHostAdapter(self.config, runner=boundary, api_probe=lambda: True)
        self.directory = self.f.base / "lifecycle"
        self.directory.mkdir(mode=0o700)
        self.binding = {"image_id": self.config.image_id,
            "compose_sha256": self.config.compose_sha256,
            "volume_sha256": self.config.volume_sha256}
        data = json.loads(self.f.data)
        for release in data["releases"]:
            release["version"] = "2.0.0"
        self.catalog = json.dumps(data).encode()
        self.make()
        self.prepared = self.f.call("stage")["request_id"]
        self.store_id = self.f.service._binding()
        self.target = activation._generation_document(
            {r.engine: r for r in self.f.service.catalog.releases})["generation_id"]

    def make(self, *, directory=None, catalog_bytes=None):
        self.link = InstallerLifecycle(directory or self.directory, self.f.policy.store,
            self.driver, self.binding, verify_volume=lambda: True,
            verify_exclusive_host=lambda: True)
        self.f.service = installer.Installer(self.f.policy, self.f.credentials,
            self.catalog if catalog_bytes is None else catalog_bytes,
            verify_volume=lambda: True, workers_stopped=lambda: self.fail("legacy stop called"),
            runtime=self.link)

    def activate(self):
        return self.f.call("activate", target=self.prepared, ident=IDENT)

    def action(self, name, **kwargs):
        return self.f.call(name, target=IDENT, **kwargs)

    def transaction(self):
        return self.f.policy.store / "transactions" / ("t-" + IDENT + ".json")

    def test_authenticated_switch_orders_pause_stop_store_start_then_explicit_resume(self):
        original = activation._atomic_json
        def observe(path, value):
            if path == self.f.policy.store / "ACTIVE.json":
                self.assertFalse(self.runner.running)
                self.assertTrue(self.control.maintenance_pending())
                self.events.append("active")
            return original(path, value)
        with patch.object(activation, "_atomic_json", side_effect=observe):
            result = self.activate()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "ready_paused", result)
        self.assertEqual(self.events, ["maintenance-begin", "stop", "active", "start"])
        self.assertTrue(result["dispatch_blocked"])
        self.assertEqual(json.loads(self.transaction().read_bytes())["state"], "activated")
        calls = len(self.runner.calls)
        self.assertEqual(self.activate(), result)
        self.assertEqual(len(self.runner.calls), calls)
        self.assertEqual(self.f.call("stage")["error"], "recovery_required")
        self.assertEqual(self.action("resume")["state"], "complete")
        self.assertEqual(self.action("resume")["state"], "complete")
        self.assertEqual(self.events.count("maintenance-end"), 1)
        self.assertEqual(self.f.call("stage")["state"], "prepared")

    def test_committed_store_rolls_back_after_failed_runtime_start_and_restart(self):
        self.fail_start = True
        self.assertFalse(self.activate()["ok"])
        self.assertEqual(json.loads(self.transaction().read_bytes())["state"], "activated")
        self.assertEqual(activation.active_generation(self.f.policy.store, self.store_id)["generation_id"],
                         self.target)
        self.make()
        self.fail_start = False
        result = self.action("rollback")
        self.assertEqual(result["state"], "restored_paused", result)
        self.assertTrue(result["dispatch_blocked"])
        self.assertEqual(activation.active_generation(self.f.policy.store, self.store_id)["generation_id"],
                         self.old)
        self.assertEqual(json.loads(self.transaction().read_bytes())["state"], "restored")
        self.assertEqual(self.runner.generation, self.old)
        self.assertEqual(self.action("rollback")["state"], "restored_paused")
        self.assertEqual(self.action("resume")["state"], "complete")

    def test_failed_health_rolls_back_running_target_and_keeps_maintenance(self):
        self.fail_health = True
        self.assertFalse(self.activate()["ok"])
        self.assertEqual(self.runner.generation, self.target)
        self.fail_health = False
        result = self.action("rollback")
        self.assertEqual(result["state"], "restored_paused", result)
        self.assertTrue(self.control.maintenance_pending())
        self.assertEqual(self.runner.generation, self.old)

    def test_store_restore_intent_survives_pointer_write_failure(self):
        self.assertEqual(self.activate()["state"], "ready_paused")
        original = activation._atomic_json
        def fail(path, value):
            if path == self.f.policy.store / "ACTIVE.json" and value["generation_id"] == self.old:
                raise OSError("synthetic write failure")
            return original(path, value)
        with patch.object(activation, "_atomic_json", side_effect=fail):
            self.assertFalse(self.action("rollback")["ok"])
        self.assertEqual(json.loads(self.transaction().read_bytes())["state"], "restoring")
        with self.assertRaises(activation.ActivationError):
            activation.recover_transaction(self.f.policy.store, self.store_id,
                "t-" + IDENT, "abort", lambda: True)
        self.make()
        self.assertEqual(self.action("rollback")["state"], "restored_paused")

    def test_store_restore_final_receipt_failure_is_restartable(self):
        self.assertEqual(self.activate()["state"], "ready_paused")
        original = activation._atomic_json
        def fail(path, value):
            if path == self.transaction() and value.get("state") == "restored":
                raise OSError("synthetic commit failure")
            return original(path, value)
        with patch.object(activation, "_atomic_json", side_effect=fail):
            self.assertFalse(self.action("rollback")["ok"])
        self.assertEqual(activation.active_generation(self.f.policy.store, self.store_id)["generation_id"],
                         self.old)
        self.make()
        self.assertEqual(self.action("rollback")["state"], "restored_paused")

    def test_generic_recover_cannot_adopt_runtime_failure(self):
        self.fail_start = True
        self.assertFalse(self.activate()["ok"])
        result = self.f.call("recover", target=IDENT, action="adopt")
        self.assertEqual(result["error"], "runtime_rollback_or_resume_required")
        self.fail_start = False
        self.assertEqual(self.action("rollback")["state"], "restored_paused")

    def test_auth_scope_and_request_schema_protect_runtime_actions(self):
        self.assertEqual(self.activate()["state"], "ready_paused")
        calls = len(self.runner.calls)
        for op in ("rollback", "resume"):
            self.assertEqual(self.action(op, token=core.OTHER_TOKEN)["error"], "forbidden")
            self.assertEqual(self.action(op, secure=False)["error"], "secure_transport_required")
            self.assertEqual(self.action(op, path="/etc")["error"], "invalid_request")
        self.assertEqual(len(self.runner.calls), calls)
        self.assertTrue(self.control.maintenance_pending())

    def test_principal_with_recover_scope_cannot_take_another_receipt(self):
        self.assertEqual(self.activate()["state"], "ready_paused")
        creds = [self.f.credentials[0], replace(self.f.credentials[1], scopes=installer.SCOPES)]
        self.f.service = installer.Installer(self.f.policy, creds, self.catalog,
            verify_volume=lambda: True, workers_stopped=lambda: False, runtime=self.link)
        self.assertEqual(self.action("rollback", token=core.OTHER_TOKEN)["error"], "forbidden")

    def test_pending_catalog_does_not_prevent_owned_runtime_rollback(self):
        self.fail_start = True
        self.assertFalse(self.activate()["ok"])
        self.make(catalog_bytes=json.dumps(
            {"schema": 1, "releases": [], "pending": list(core.catalog.ENTRYPOINTS)}).encode())
        self.fail_start = False
        self.assertEqual(self.action("rollback")["state"], "restored_paused")

    def test_lock_overlap_is_rejected_before_dispatch(self):
        with self.assertRaises(Exception):
            self.make(directory=self.f.control)

    def test_store_rollback_rejects_wrong_binding_and_missing_stop_proof(self):
        self.assertEqual(self.activate()["state"], "ready_paused")
        for previous, stopped in ((self.target, lambda: True), (self.old, lambda: False)):
            with self.subTest(previous=previous), self.assertRaises(activation.ActivationError):
                activation.restore_committed_generation(self.f.policy.store, self.store_id,
                    "t-" + IDENT, self.target, previous, stopped)
        self.assertEqual(activation.active_generation(self.f.policy.store, self.store_id)["generation_id"],
                         self.target)

    def test_runtime_operations_are_unavailable_without_provisioning(self):
        service = self.f.make(catalog_bytes=self.catalog)
        reply = service.dispatch("Bearer " + core.TOKEN,
            json.dumps({"protocol": 1, "operation": "rollback", "target": IDENT}).encode(),
            secure_channel=True)
        self.assertEqual(reply["error"], "runtime_adapter_required")

    def test_failure_after_active_replace_still_has_a_guarded_store_rollback(self):
        original = activation._atomic_json
        def fail_after_replace(path, value):
            original(path, value)
            if path == self.f.policy.store / "ACTIVE.json" and value["generation_id"] == self.target:
                raise OSError("synthetic lost fsync acknowledgement")
        with patch.object(activation, "_atomic_json", side_effect=fail_after_replace):
            self.assertFalse(self.activate()["ok"])
        self.assertEqual(json.loads(self.transaction().read_bytes())["state"], "failed")
        self.assertEqual(activation.active_generation(self.f.policy.store, self.store_id)["generation_id"],
                         self.target)
        self.make()
        self.assertEqual(self.action("rollback")["state"], "restored_paused")

    def test_lost_installer_resume_receipt_does_not_repeat_resume(self):
        self.assertEqual(self.activate()["state"], "ready_paused")
        save = self.f.service._save
        def fail(row):
            if row.get("state") == "complete":
                raise OSError("synthetic receipt failure")
            save(row)
        with patch.object(self.f.service, "_save", side_effect=fail):
            self.assertFalse(self.action("resume")["ok"])
        self.assertFalse(self.control.maintenance_pending())
        self.make()
        self.assertEqual(self.action("resume")["state"], "complete")
        self.assertEqual(self.events.count("maintenance-end"), 1)

    def test_store_rechecks_expected_candidate_generation_before_any_switch(self):
        row = json.loads((self.f.control / "records" / (self.prepared + ".json")).read_bytes())
        with self.assertRaisesRegex(activation.ActivationError, "candidate_generation_changed"):
            activation.activate_generation(self.f.policy.store, self.store_id,
                row["candidates"], lambda: self.fail("must not stop"),
                transaction_id="t-" + IDENT, expected_generation=self.old)
        self.assertFalse(self.transaction().exists())
        self.assertEqual(activation.active_generation(self.f.policy.store, self.store_id)["generation_id"],
                         self.old)

    @unittest.skipUnless(__import__("sys").platform == "linux", "Linux Unix peer transport")
    def test_real_unix_transport_routes_rollback_and_resume_on_mutation_lane(self):
        import os
        import socket
        import struct
        import time
        import installer_transport as transport
        import pairing_registry as pairing
        directory = self.f.base / "sockets"
        directory.mkdir(mode=0o700)
        registry_path = self.f.base / "registry"
        registry_path.mkdir(mode=0o700)
        registry = pairing.Registry(registry_path, pairing.initialize(registry_path))
        token = registry.issue("homeassistant", installer.SCOPES)
        service = installer.Installer(self.f.policy, (), self.catalog,
            verify_volume=lambda: True, workers_stopped=lambda: False,
            credential_provider=registry.snapshot, runtime=self.link)
        with transport.UnixInstallerServer(directory, service, registry,
                client_uid=os.geteuid(), client_gid=os.getegid(), io_timeout=5):
            client = transport.UnixInstallerClient(directory, host_id=registry.host_id,
                server_uid=os.geteuid(), timeout=5)
            result = client.request(token, {"protocol": 1, "operation": "activate",
                "target": self.prepared, "request_id": IDENT})
            self.assertEqual(result["state"], "ready_paused", result)
            body = json.dumps({"protocol": 1, "operation": "resume", "target": IDENT}).encode()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.connect(str(directory / "control.sock"))
                conn.sendall(transport._request_frame(registry.host_id, "Bearer " + token, body))
                deadline = time.monotonic() + 5
                length, = struct.unpack("!I", transport._read(conn, 4, deadline))
                reply = json.loads(transport._read(conn, length, deadline))
                self.assertEqual(reply["result"]["error"], "wrong_lane")
            self.assertTrue(self.control.maintenance_pending())
            result = client.request(token, {"protocol": 1, "operation": "rollback", "target": IDENT})
            self.assertEqual(result["state"], "restored_paused", result)
            result = client.request(token, {"protocol": 1, "operation": "resume", "target": IDENT})
            self.assertEqual(result["state"], "complete", result)
        result = client.request(token, {"protocol": 1, "operation": "resume", "target": IDENT})
        self.assertEqual(result["outcome"], "unknown")
        self.assertEqual(result["request_id"], IDENT)


class FirstInstallCouplingTests(unittest.TestCase):
    """Restricted installer routes an absent runtime through FirstInstall."""

    def setUp(self):
        self.f = core.InstallerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.prepared = self.f.ready()
        self.d = runtime.AdapterTests()
        self.d.setUp()
        self.addCleanup(self.d.doCleanups)
        self.config = replace(self.d.config, store=self.f.policy.store)
        self.runner = runtime.FakeRunner(self.config)
        self.runner.present = False
        self.driver = docker.DockerHostAdapter(
            self.config, runner=self.runner, api_probe=lambda: True)
        self.directory = self.f.base / "lifecycle"
        self.directory.mkdir(mode=0o700)
        self.binding = {"image_id": self.config.image_id,
            "compose_sha256": self.config.compose_sha256,
            "volume_sha256": self.config.volume_sha256}
        self.make()
        self.store_id = self.f.service._binding()
        self.target = activation._generation_document(
            {r.engine: r for r in self.f.service.catalog.releases})["generation_id"]

    def make(self):
        self.link = InstallerLifecycle(
            self.directory, self.f.policy.store, self.driver, self.binding,
            verify_volume=lambda: True, verify_exclusive_host=lambda: True)
        self.f.service = installer.Installer(
            self.f.policy, self.f.credentials, self.f.data,
            verify_volume=lambda: True,
            workers_stopped=lambda: self.fail("legacy stop called"),
            runtime=self.link)

    def activate(self):
        return self.f.call("activate", target=self.prepared, ident=IDENT)

    def action(self, name, **kwargs):
        return self.f.call(name, target=IDENT, **kwargs)

    def test_authenticated_first_install_can_resume_after_adapter_restart(self):
        result = self.activate()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "ready_paused", result)
        self.assertTrue(result["dispatch_blocked"])
        self.assertEqual(
            activation.active_generation(self.f.policy.store, self.store_id)["generation_id"],
            self.target)
        self.assertTrue(self.runner.present)
        self.assertTrue((self.config.data / "run/container-maintenance.json").is_file())
        self.make()
        result = self.action("resume")
        self.assertEqual(result["state"], "complete", result)
        self.assertFalse(result["dispatch_blocked"])
        self.assertFalse((self.config.data / "run/container-maintenance.json").exists())
        self.assertEqual(self.action("resume"), result)

    def test_authenticated_first_install_rolls_back_to_absence(self):
        result = self.activate()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "ready_paused", result)
        calls = len(self.runner.calls)
        self.assertEqual(
            self.action("rollback", token=core.OTHER_TOKEN)["error"], "forbidden")
        self.assertEqual(len(self.runner.calls), calls)
        self.make()
        result = self.action("rollback")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "rolled_back_absent", result)
        self.assertFalse(result["dispatch_blocked"])
        self.assertIsNone(
            activation.active_generation(self.f.policy.store, self.store_id))
        self.assertFalse(self.runner.present)
        self.assertFalse((self.config.data / "run/container-maintenance.json").exists())
        self.assertEqual(self.action("rollback"), result)


if __name__ == "__main__":
    unittest.main()
