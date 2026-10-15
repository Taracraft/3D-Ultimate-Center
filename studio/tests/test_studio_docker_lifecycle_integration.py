"""Adapter/lifecycle/JobControl integration with a synthetic Docker boundary."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("adapter_fixture",
    Path(__file__).with_name("test_studio_docker_host_adapter.py"))
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
OLD, NEW, IDENT = fixture_module.OLD, fixture_module.NEW, fixture_module.IDENT
import docker_host_adapter as docker
import host_lifecycle as lifecycle

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("integration_job_control",
    ROOT / "deploy/homeassistant/host/3d-printer-slicing-server/job_control.py")
job_control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job_control)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.AdapterTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.adapter = self.fixture.adapter
        self.runner = self.fixture.runner
        self.config = self.fixture.config
        self.control = job_control.JobControl(self.config.data)
        self.fail_start = False
        self.restores = []
        def boundary(argv, *, env, timeout):
            if argv[1:3] == ("container", "exec"):
                operation, ident = argv[8], argv[10]
                callback = (self.control.begin_maintenance if operation == "maintenance-begin"
                            else self.control.end_maintenance)
                return docker.Result(0, json.dumps(callback(ident)).encode(), b"")
            if argv[1] == "compose" and self.fail_start:
                raise docker.DockerAdapterError("synthetic_start_failure")
            return self.runner(argv, env=env, timeout=timeout)
        self.adapter.runner = boundary
        self.directory = self.fixture.root / "lifecycle"
        self.directory.mkdir(mode=0o700)
        self.engine = self.make_lifecycle()
        self.target = dict(self.adapter.snapshot()["binding"], generation_id=NEW)

    def set_active(self, generation):
        (self.config.store / "ACTIVE.json").write_text(json.dumps(
            {"schema": 1, "generation_id": generation}))

    def restore(self, generation):
        self.assertFalse(self.runner.running)
        self.assertTrue(self.adapter.paused(IDENT))
        self.restores.append(generation)
        self.set_active(generation)

    def make_lifecycle(self):
        return lifecycle.Lifecycle(self.directory, self.adapter,
            verify_volume=lambda: True,
            active_generation=self.adapter._active_generation_hint,
            activate=self.set_active, restore=self.restore)

    def test_full_switch_stays_paused_until_explicit_resume(self):
        result = self.engine.switch(IDENT, self.target)
        self.assertEqual(result["state"], "ready_paused")
        self.assertTrue(self.control.maintenance_pending())
        self.assertEqual(self.control._maintenance_record()["request_id"], IDENT)
        self.assertEqual(self.engine.resume(IDENT)["state"], "complete")
        self.assertFalse(self.control.maintenance_pending())

    def test_failed_start_restores_stopped_pair_after_orchestrator_restart(self):
        self.fail_start = True
        with self.assertRaisesRegex(docker.DockerAdapterError, "synthetic_start"):
            self.engine.switch(IDENT, self.target)
        self.assertEqual(self.engine.status()["state"], "starting")
        self.assertFalse(self.runner.running)
        self.assertEqual(self.adapter._active_generation_hint(), NEW)
        self.assertEqual(self.runner.generation, OLD)
        before = len([c for c in self.runner.calls if c[0][1:3] == ("container", "stop")])
        self.fail_start = False
        restored = self.make_lifecycle().rollback(IDENT)
        self.assertEqual(restored["state"], "restored_paused")
        self.assertEqual(self.restores, [OLD])
        self.assertTrue(self.control.maintenance_pending())
        self.assertEqual(self.adapter._active_generation_hint(), OLD)
        after = len([c for c in self.runner.calls if c[0][1:3] == ("container", "stop")])
        self.assertEqual(before, after)
        self.assertEqual(self.make_lifecycle().rollback(IDENT)["state"], "restored_paused")
        self.assertEqual(self.restores, [OLD])

    def test_stopped_pair_proof_is_fresh_and_stop_is_idempotent(self):
        proof = self.adapter.snapshot()
        self.adapter.stop(proof)
        stopped = self.adapter.snapshot()
        self.assertFalse(stopped["running"])
        count = len(self.runner.calls)
        self.adapter.stop(stopped)
        self.assertFalse(any(c[0][1:3] == ("container", "stop")
                             for c in self.runner.calls[count:]))
        self.assertTrue(self.adapter.stopped(stopped))

    def test_stopped_foreign_mount_cannot_reach_store_restore(self):
        self.fail_start = True
        with self.assertRaises(docker.DockerAdapterError):
            self.engine.switch(IDENT, self.target)
        self.runner.bad = "mount"
        with self.assertRaises(docker.DockerAdapterError):
            self.engine.rollback(IDENT)
        self.assertEqual(self.restores, [])
        self.assertTrue(self.control.maintenance_pending())

    def test_mixed_or_unknown_running_states_require_reconciliation(self):
        rows = self.runner.rows
        for value in (False, None, 0):
            def changed():
                values = rows()
                values[1]["State"]["Running"] = value
                return values
            with self.subTest(value=value), patch.object(self.runner, "rows", changed):
                with self.assertRaisesRegex(docker.DockerAdapterError, "reconciliation"):
                    self.adapter.snapshot()
        self.runner.running = False
        for flag in ("Paused", "Restarting", "Dead"):
            def flagged():
                values = rows()
                values[0]["State"][flag] = True
                return values
            with self.subTest(flag=flag), patch.object(self.runner, "rows", flagged):
                with self.assertRaises(docker.DockerAdapterError):
                    self.adapter.snapshot()

    def test_changed_identity_does_not_issue_stop(self):
        proof = self.adapter.snapshot()
        self.runner.ids["api"] = "f" * 64
        with self.assertRaisesRegex(docker.DockerAdapterError, "ownership"):
            self.adapter.stop(proof)
        self.assertFalse(any(c[0][1:3] == ("container", "stop")
                             for c in self.runner.calls))

    def marker(self, raw):
        path = self.config.data / "run/container-maintenance.json"
        path.write_bytes(raw)
        path.chmod(0o600)
        return path

    def test_duplicate_and_wrong_type_markers_are_rejected_by_both_readers(self):
        samples = [
            ('{"schema":1,"request_id":"' + "b"*32 + '","request_id":"' + IDENT +
             '","state":"maintenance"}').encode(),
            json.dumps({"schema": True, "request_id": IDENT, "state": "maintenance"}).encode(),
            json.dumps({"schema": 1, "request_id": 123, "state": "maintenance"}).encode(),
            b"[]", b"{", b"\xff",
        ]
        for raw in samples:
            with self.subTest(raw=raw):
                self.marker(raw)
                with self.assertRaises((ValueError, TypeError)):
                    self.control._maintenance_record()
                with self.assertRaises(docker.DockerAdapterError):
                    self.adapter.paused(IDENT)

    def test_oversized_marker_is_rejected_before_open(self):
        self.marker(b"x" * 4097)
        with patch.object(docker.os, "open", side_effect=AssertionError("must not open")):
            with self.assertRaisesRegex(docker.DockerAdapterError, "maintenance_proof"):
                self.adapter.paused(IDENT)

    def test_file_replaced_between_check_and_open_is_rejected(self):
        path = self.marker(json.dumps(
            {"schema": 1, "request_id": IDENT, "state": "maintenance"}).encode())
        other = self.fixture.root / "other"
        other.write_bytes(path.read_bytes())
        other.chmod(0o600)
        original = os.open
        with patch.object(docker.os, "open", lambda p, flags: original(other, flags)):
            with self.assertRaisesRegex(docker.DockerAdapterError, "maintenance_proof"):
                self.adapter.paused(IDENT)

    @unittest.skipUnless(os.name == "posix", "POSIX marker permissions and links")
    def test_posix_marker_modes_and_links_are_rejected(self):
        path = self.marker(json.dumps(
            {"schema": 1, "request_id": IDENT, "state": "maintenance"}).encode())
        path.chmod(0o400)
        with self.assertRaises(docker.DockerAdapterError):
            self.adapter.paused(IDENT)
        path.chmod(0o600)
        link = path.with_name("hardlink")
        os.link(path, link)
        with self.assertRaises(docker.DockerAdapterError):
            self.adapter.paused(IDENT)
        link.unlink()
        path.unlink()
        path.symlink_to(link)
        with self.assertRaises(docker.DockerAdapterError):
            self.adapter.paused(IDENT)


if __name__ == "__main__":
    unittest.main()
