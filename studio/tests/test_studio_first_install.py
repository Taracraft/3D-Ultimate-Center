"""Synthetic durable first-install transaction tests; no Docker daemon or engine."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Slicer-Server"))
import first_install as bootstrap

IDENT = "a" * 32
OTHER = "b" * 32
PRINCIPAL = hashlib.sha256(b"homeassistant").hexdigest()
OTHER_PRINCIPAL = hashlib.sha256(b"other").hexdigest()
STORE = "c" * 32
GENERATION = "g-" + "d" * 64
TARGET = {"generation_id": GENERATION, "image_id": "sha256:" + "e" * 64,
          "compose_sha256": "f" * 64, "volume_sha256": "1" * 64}


class Driver:
    def __init__(self):
        self.target = dict(TARGET)
        self.state = "empty"
        self.maintenance = None
        self.ids = {"api": "2" * 64, "worker": "3" * 64}
        self.events = []
        self.fail_start_after_mutation = False

    def proof(self, running=True):
        return {"binding": dict(self.target), "containers": dict(self.ids),
                "running": running, "mounts_verified": True,
                "isolation_verified": True}

    def installation_state(self):
        return {"state": self.state,
                "runtime": None if self.state == "empty" else
                           self.proof(self.state == "running"),
                "installation_permitted": False}

    def bootstrap_runtime(self, target):
        if target != self.target:
            raise ValueError("binding")
        return None if self.state == "empty" else self.proof(self.state == "running")

    def prepare_first_install(self, target, request_id):
        self.events.append("barrier")
        if target != self.target:
            raise ValueError("binding")
        if self.maintenance not in (None, request_id):
            raise ValueError("foreign")
        self.maintenance = request_id
        return {"state": "first_install_maintenance", "request_id": request_id,
                "dispatch_blocked": True, "runtime_absent": True}

    def paused(self, request_id):
        return self.maintenance == request_id

    def start(self, target):
        self.events.append("start")
        if target != self.target:
            raise ValueError("binding")
        self.state = "running"
        if self.fail_start_after_mutation:
            self.fail_start_after_mutation = False
            raise OSError("synthetic lost start reply")

    def health(self, target):
        self.events.append("health")
        return {"runtime": self.proof(True), "api_tls_authenticated": True,
                "worker_healthy": True, "maintenance_id": self.maintenance}

    def snapshot(self):
        return self.proof(self.state == "running")

    def stop(self, proof):
        self.events.append("stop")
        if proof["containers"] != self.ids:
            raise ValueError("identity")
        self.state = "stopped"

    def stopped(self, proof):
        return self.state == "stopped" and proof["containers"] == self.ids

    def remove(self, proof):
        self.events.append("remove")
        if not self.stopped(proof):
            raise ValueError("not stopped")
        self.state = "empty"

    def clear_first_install(self, request_id, generation_id):
        self.events.append("clear")
        if self.state != "empty" or self.maintenance != request_id or generation_id != GENERATION:
            raise ValueError("clear")
        self.maintenance = None

    def resume(self, request_id):
        self.events.append("resume")
        if self.maintenance != request_id:
            raise ValueError("owner")
        self.maintenance = None

    def resumed(self, request_id):
        return self.maintenance is None


class FirstInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        if os.name != "nt":
            self.base.chmod(0o700)
        self.control = self.base / "control"
        self.control.mkdir(mode=0o700)
        self.driver = Driver()
        self.active = None
        self.transactions = {}
        self.volume = True
        self.store_valid = True
        self.exclusive = True

    def activate(self, generation, transaction):
        if self.active is not None:
            raise ValueError("active")
        self.transactions[transaction] = {"target": generation, "previous": None}
        self.active = generation

    def deactivate(self, generation, transaction):
        row = self.transactions.get(transaction)
        if row != {"target": generation, "previous": None}:
            raise ValueError("binding")
        if self.active not in (None, generation):
            raise ValueError("active")
        self.active = None

    def make(self):
        return bootstrap.FirstInstall(
            self.control, self.driver, verify_volume=lambda: self.volume,
            verify_store=lambda value: self.store_valid and value == STORE,
            verify_exclusive_host=lambda: self.exclusive,
            active_generation=lambda: self.active, activate=self.activate,
            deactivate=self.deactivate)

    def install(self, **kwargs):
        return self.make().install(kwargs.get("request_id", IDENT),
                                   kwargs.get("principal", PRINCIPAL),
                                   kwargs.get("store", STORE),
                                   kwargs.get("target", TARGET))

    def test_complete_install_remains_paused_until_bound_resume(self):
        result = self.install()
        self.assertEqual(result["state"], "ready_paused")
        self.assertTrue(result["dispatch_blocked"])
        self.assertEqual(self.active, GENERATION)
        self.assertEqual(self.driver.events, ["barrier", "start", "health"])
        completed = self.make().resume(IDENT, PRINCIPAL)
        self.assertEqual(completed["state"], "complete")
        self.assertFalse(completed["dispatch_blocked"])
        self.assertEqual(self.make().resume(IDENT, PRINCIPAL), completed)
        self.assertEqual(self.driver.events.count("resume"), 1)

    def test_lost_start_reply_is_reconciled_by_explicit_absent_rollback(self):
        self.driver.fail_start_after_mutation = True
        with self.assertRaises(OSError):
            self.install()
        self.assertEqual(self.make().status()["state"], "starting")
        result = self.make().rollback(IDENT, PRINCIPAL)
        self.assertEqual(result["state"], "rolled_back_absent")
        self.assertFalse(result["dispatch_blocked"])
        self.assertIsNone(self.active)
        self.assertEqual(self.driver.state, "empty")
        self.assertIsNone(self.driver.maintenance)
        self.assertEqual(self.driver.events[-3:], ["stop", "remove", "clear"])
        self.assertEqual(self.make().rollback(IDENT, PRINCIPAL), result)

    def test_lost_activation_reply_without_runtime_rolls_back_to_absence(self):
        original = self.activate
        def lost(generation, transaction):
            original(generation, transaction)
            raise OSError("synthetic lost activation reply")
        instance = bootstrap.FirstInstall(
            self.control, self.driver, verify_volume=lambda: True, verify_store=lambda value: value == STORE,
            verify_exclusive_host=lambda: self.exclusive,
            active_generation=lambda: self.active, activate=lost,
            deactivate=self.deactivate)
        with self.assertRaises(OSError):
            instance.install(IDENT, PRINCIPAL, STORE, TARGET)
        result = self.make().rollback(IDENT, PRINCIPAL)
        self.assertEqual(result["state"], "rolled_back_absent")
        self.assertNotIn("remove", self.driver.events)
        self.assertIsNone(self.active)

    def test_request_principal_store_and_runtime_binding_are_immutable(self):
        self.install()
        cases = [
            (dict(principal=OTHER_PRINCIPAL), "request_id_conflict"),
            (dict(store="9" * 32), "persistent_store_unverified"),
            (dict(target={**TARGET, "image_id": "sha256:" + "8" * 64}),
             "request_id_conflict"),
        ]
        for values, error in cases:
            with self.subTest(values=values), self.assertRaisesRegex(
                    bootstrap.FirstInstallError, error):
                self.install(**values)
        with self.assertRaisesRegex(bootstrap.FirstInstallError,
                                    "principal_mismatch"):
            self.make().resume(IDENT, OTHER_PRINCIPAL)

    def test_foreign_request_and_existing_active_are_blocked_before_mutation(self):
        self.install()
        with self.assertRaisesRegex(bootstrap.FirstInstallError,
                                    "first_install_recovery_required"):
            self.install(request_id=OTHER)
        self.assertEqual(self.driver.events.count("barrier"), 1)
        other = FirstInstallTests("runTest")
        del other
        with tempfile.TemporaryDirectory() as tmp:
            control = Path(tmp)
            if os.name != "nt":
                control.chmod(0o700)
            self.driver.state = "empty"
            self.driver.maintenance = None
            self.active = GENERATION
            instance = bootstrap.FirstInstall(
                control, self.driver, verify_volume=lambda: True, verify_store=lambda value: value == STORE,
                verify_exclusive_host=lambda: self.exclusive,
                active_generation=lambda: self.active, activate=self.activate,
                deactivate=self.deactivate)
            with self.assertRaisesRegex(bootstrap.FirstInstallError,
                                        "active_generation_already_exists"):
                instance.install(OTHER, PRINCIPAL, STORE, TARGET)

    def test_parallel_runtime_is_blocked_before_journal_or_driver_mutation(self):
        self.exclusive = False
        with self.assertRaisesRegex(bootstrap.FirstInstallError,
                                    "parallel_slicer_runtime_detected"):
            self.install()
        self.assertFalse((self.control / "FIRST_INSTALL.json").exists())
        self.assertEqual(self.driver.events, [])

    def test_exclusivity_is_rechecked_after_barrier_before_activation(self):
        checks = iter((True, False))
        instance = bootstrap.FirstInstall(
            self.control, self.driver, verify_volume=lambda: True,
            verify_store=lambda value: value == STORE,
            verify_exclusive_host=lambda: next(checks),
            active_generation=lambda: self.active, activate=self.activate,
            deactivate=self.deactivate)
        with self.assertRaisesRegex(bootstrap.FirstInstallError,
                                    "parallel_slicer_runtime_detected"):
            instance.install(IDENT, PRINCIPAL, STORE, TARGET)
        self.assertIsNone(self.active)
        self.assertEqual(self.driver.events, ["barrier"])
        self.assertEqual(instance.status()["state"], "barrier")

    def test_volume_and_observation_fail_closed_before_journal_mutation(self):
        self.volume = False
        with self.assertRaisesRegex(bootstrap.FirstInstallError,
                                    "persistent_volume_unverified"):
            self.install()
        self.assertFalse((self.control / "FIRST_INSTALL.json").exists())
        self.volume = True
        self.driver.state = "stopped"
        with self.assertRaisesRegex(bootstrap.FirstInstallError,
                                    "installation_state_mismatch"):
            self.install()
        self.assertFalse((self.control / "FIRST_INSTALL.json").exists())
        self.driver.state = "empty"
        self.store_valid = False
        with self.assertRaisesRegex(bootstrap.FirstInstallError,
                                    "persistent_store_unverified"):
            self.install()
        self.assertFalse((self.control / "FIRST_INSTALL.json").exists())

    def test_completed_or_rolled_back_receipt_is_archived_before_new_request(self):
        self.install()
        self.make().rollback(IDENT, PRINCIPAL)
        result = self.install(request_id=OTHER)
        self.assertEqual(result["state"], "ready_paused")
        self.assertTrue((self.control / "receipts" / (IDENT + ".json")).is_file())
        self.assertEqual(self.driver.events.count("barrier"), 2)

    def test_resume_rejects_changed_container_identity(self):
        self.install()
        self.driver.ids["api"] = "4" * 64
        with self.assertRaisesRegex(bootstrap.FirstInstallError,
                                    "runtime_health_rejected"):
            self.make().resume(IDENT, PRINCIPAL)
        self.assertEqual(self.make().status()["state"], "ready_paused")

    def test_tampered_or_duplicate_journal_is_rejected(self):
        self.install()
        path = self.control / "FIRST_INSTALL.json"
        value = json.loads(path.read_text())
        value["store_id"] = "invalid"
        path.write_text(json.dumps(value))
        if os.name != "nt":
            path.chmod(0o600)
        with self.assertRaises(bootstrap.FirstInstallError):
            self.make().status()
        path.write_text('{"schema":1,"schema":1}')
        if os.name != "nt":
            path.chmod(0o600)
        with self.assertRaises(bootstrap.FirstInstallError):
            self.make().status()

    def test_lost_resume_receipt_does_not_repeat_runtime_resume(self):
        self.install()
        instance = self.make()
        original = instance._save
        def lost(row, phase):
            original(row, phase)
            if phase == "complete":
                raise OSError("synthetic lost final receipt")
        with patch.object(instance, "_save", side_effect=lost), self.assertRaises(OSError):
            instance.resume(IDENT, PRINCIPAL)
        self.assertEqual(self.make().resume(IDENT, PRINCIPAL)["state"], "complete")
        self.assertEqual(self.driver.events.count("resume"), 1)


if __name__ == "__main__":
    unittest.main()
