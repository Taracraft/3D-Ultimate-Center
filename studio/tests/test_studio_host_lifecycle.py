"""Lifecycle acceptance with synthetic store/runtime; never Docker or real jobs."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Slicer-Server"))
import host_lifecycle as life

IDENT = "a" * 32
OTHER = "b" * 32
OLD = {"generation_id": "g-" + "1" * 64, "image_id": "sha256:" + "2" * 64,
       "compose_sha256": "3" * 64, "volume_sha256": "4" * 64}
NEW = {**OLD, "generation_id": "g-" + "5" * 64, "compose_sha256": "6" * 64}


class Runtime:
    def __init__(self):
        self.binding = copy.deepcopy(OLD)
        self.ids = {"api": "7" * 64, "worker": "8" * 64}
        self.running = True
        self.marker = None
        self.calls = []
        self.fail = None
        self.active = OLD["generation_id"]

    def call(self, name):
        self.calls.append(name)
        if self.fail == name:
            raise TimeoutError("synthetic secret never returned")

    def snapshot(self):
        self.call("snapshot")
        return {"binding": copy.deepcopy(self.binding), "containers": dict(self.ids),
                "running": self.running, "mounts_verified": True, "isolation_verified": True}

    def pause(self, ident):
        self.call("pause")
        self.marker = ident

    def paused(self, ident):
        self.call("paused")
        return self.marker == ident

    def stop(self, proof):
        self.call("stop")
        assert proof["containers"] == self.ids
        self.running = False

    def stopped(self, proof):
        self.call("stopped")
        return not self.running and self.ids == proof["containers"]

    def start(self, expected):
        self.call("start")
        assert not self.running and self.marker in (IDENT, OTHER)
        self.binding = copy.deepcopy(expected)
        self.ids = {"api": "9" * 64, "worker": "0" * 64}
        self.running = True

    def health(self, expected):
        self.call("health")
        return {"runtime": self.snapshot(), "api_tls_authenticated": True,
                "worker_healthy": True, "maintenance_id": self.marker}

    def resume(self, ident):
        self.call("resume")
        assert self.marker == ident
        self.marker = None

    def resumed(self, ident):
        self.call("resumed")
        return self.marker is None

    def activate(self, value):
        self.call("activate")
        assert not self.running and self.marker in (IDENT, OTHER)
        self.active = value

    def restore(self, value):
        self.call("restore")
        assert not self.running and self.marker in (IDENT, OTHER)
        self.active = value


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.runtime = Runtime()
        self.volume = True
        self.flow = self.create()

    def create(self):
        return life.Lifecycle(self.root, self.runtime, verify_volume=lambda: self.volume,
                              active_generation=lambda: self.runtime.active,
                              activate=self.runtime.activate, restore=self.runtime.restore)

    def ready(self):
        return self.flow.switch(IDENT, NEW)

    def test_success_remains_paused_until_explicit_resume(self):
        result = self.ready()
        self.assertEqual(result["state"], "ready_paused")
        self.assertTrue(result["dispatch_blocked"])
        self.assertFalse(result["requires_recovery"])
        self.assertEqual(self.runtime.marker, IDENT)
        self.assertNotIn("resume", self.runtime.calls)
        self.assertLess(self.runtime.calls.index("stop"), self.runtime.calls.index("activate"))
        self.assertLess(self.runtime.calls.index("activate"), self.runtime.calls.index("start"))
        self.assertEqual(self.flow.resume(IDENT)["state"], "complete")
        self.assertIsNone(self.runtime.marker)

    def test_restart_preserves_receipt_and_duplicate_is_nonmutating(self):
        result = self.ready()
        self.flow = self.create()
        self.runtime.calls.clear()
        self.assertEqual(self.ready(), result)
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(self.flow.status(), result)

    def test_same_request_cannot_change_binding(self):
        self.ready()
        with self.assertRaisesRegex(life.LifecycleError, "request_id_conflict"):
            self.flow.switch(IDENT, {**NEW, "image_id": "sha256:" + "f" * 64})

    def test_later_transaction_preserves_receipt_and_old_retry_never_replays(self):
        self.ready()
        first = self.flow.resume(IDENT)
        before = self.flow._load()
        self.flow.switch(OTHER, OLD)
        self.assertEqual(self.flow._load(self.flow.receipts/(IDENT+".json")), before)
        self.runtime.calls.clear()
        self.assertEqual(self.flow.switch(IDENT, NEW), first)
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(self.flow.status()["request_id"], OTHER)

    def test_unfinished_transaction_blocks_other_request(self):
        self.ready()
        with self.assertRaisesRegex(life.LifecycleError, "recovery_required"):
            self.flow.switch(OTHER, OLD)

    def test_receipt_capacity_never_discards_history(self):
        self.ready();self.flow.resume(IDENT)
        before = self.flow.path.read_bytes()
        with patch.object(life, "MAX_RECEIPTS", 0):
            with self.assertRaisesRegex(life.LifecycleError, "history_capacity"):
                self.flow.switch(OTHER, OLD)
        self.assertEqual(self.flow.path.read_bytes(), before)

    def test_inconsistent_completed_record_never_reports_success(self):
        self.ready()
        row = self.flow._load()
        row["result_binding"] = None
        row["result_containers"] = None
        life.storage._atomic_json(self.flow.path, row)
        with self.assertRaises(life.LifecycleError):self.flow.status()

    def test_invalid_input_and_volume_have_no_runtime_effect(self):
        for ident in ("", "../", True, "a"*31):
            with self.subTest(ident=ident), self.assertRaises(life.LifecycleError):
                self.flow.switch(ident, NEW)
        for target in ({}, {**NEW, "command": "arbitrary"}, {**NEW, "image_id": "latest"}):
            with self.subTest(target=target), self.assertRaises(life.LifecycleError):
                self.flow.switch(IDENT, target)
        self.volume = 1
        with self.assertRaisesRegex(life.LifecycleError, "persistent_volume"):
            self.ready()
        self.assertFalse(self.flow.path.exists())
        self.assertEqual(self.runtime.calls, [])

    def test_volume_identity_change_rejected_before_pause(self):
        with self.assertRaisesRegex(life.LifecycleError, "volume_mismatch"):
            self.flow.switch(IDENT, {**NEW, "volume_sha256": "f"*64})
        self.assertNotIn("pause", self.runtime.calls)

    def test_generation_mismatch_before_change(self):
        self.runtime.active = NEW["generation_id"]
        with self.assertRaisesRegex(life.LifecycleError, "active_generation"):
            self.ready()
        self.assertNotIn("pause", self.runtime.calls)

    def test_failure_boundaries_persist_recovery_and_never_resume(self):
        expected = {"pause":"pausing", "stop":"stopping", "activate":"activating",
                    "start":"starting", "health":"checking"}
        for operation, phase in expected.items():
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                runtime = Runtime()
                runtime.fail = operation
                root = Path(tmp);root.chmod(0o700)
                flow = life.Lifecycle(root, runtime, verify_volume=lambda: True,
                    active_generation=lambda: runtime.active, activate=runtime.activate,
                    restore=runtime.restore)
                with self.assertRaises(TimeoutError):
                    flow.switch(IDENT, NEW)
                self.assertEqual(flow.status()["state"], phase)
                self.assertTrue(flow.status()["requires_recovery"])
                self.assertIsNone(flow.status()["dispatch_blocked"])
                with self.assertRaisesRegex(life.LifecycleError, "recovery_required"):
                    flow.switch(IDENT, NEW)
                self.assertNotIn("resume", runtime.calls)

    def test_journal_failure_precedes_runtime_action(self):
        with patch.object(life.storage, "_atomic_json", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                self.ready()
        self.assertNotIn("pause", self.runtime.calls)

    def test_pause_proof_required_before_stop(self):
        with patch.object(self.runtime, "paused", return_value=False):
            with self.assertRaisesRegex(life.LifecycleError, "maintenance_unverified"):
                self.ready()
        self.assertNotIn("stop", self.runtime.calls)

    def test_stop_proof_required_before_generation_change(self):
        with patch.object(self.runtime, "stopped", return_value=False):
            with self.assertRaisesRegex(life.LifecycleError, "not_stopped"):
                self.ready()
        self.assertNotIn("activate", self.runtime.calls)

    def test_post_activation_volume_loss_prevents_start(self):
        original = self.flow.activate
        def activate(value):
            original(value)
            self.volume = False
        self.flow.activate = activate
        with self.assertRaisesRegex(life.LifecycleError, "persistent_volume"):
            self.ready()
        self.assertNotIn("start", self.runtime.calls)

    def test_activation_callback_must_really_change_store(self):
        self.flow.activate = lambda value: None
        with self.assertRaisesRegex(life.LifecycleError, "active_generation"):
            self.ready()
        self.assertNotIn("start", self.runtime.calls)

    def test_health_requires_authenticated_api_worker_and_owned_barrier(self):
        original = self.runtime.health
        for key, value in (("api_tls_authenticated", False), ("worker_healthy", False),
                           ("maintenance_id", OTHER)):
            with self.subTest(key=key):
                if self.flow.path.exists():self.flow.path.unlink()
                self.runtime = Runtime();self.flow = self.create()
                original = self.runtime.health
                def bad(expected):
                    result = original(expected);result[key] = value;return result
                with patch.object(self.runtime, "health", side_effect=bad):
                    with self.assertRaisesRegex(life.LifecycleError, "health_rejected"):
                        self.ready()
                self.assertEqual(self.flow.status()["state"], "checking")

    def test_runtime_proof_rejects_wrong_image_mounts_and_container_aliases(self):
        original = self.runtime.snapshot()
        for key, value in (("running", "yes"), ("mounts_verified", False),
                           ("isolation_verified", False),
                           ("containers", {"api":"a"*64, "worker":"a"*64})):
            with self.subTest(key=key):
                bad = copy.deepcopy(original);bad[key] = value
                with self.assertRaises(life.LifecycleError):
                    life._proof(bad, OLD, running=True)
        bad = copy.deepcopy(original);bad["binding"]["image_id"]="sha256:"+"f"*64
        with self.assertRaises(life.LifecycleError):life._proof(bad, OLD, running=True)

    def test_rollback_after_health_failure_restores_both_store_and_runtime(self):
        self.runtime.fail = "health"
        with self.assertRaises(TimeoutError):self.ready()
        self.runtime.fail = None
        self.flow = self.create()
        result = self.flow.rollback(IDENT)
        self.assertEqual(result["state"], "restored_paused")
        self.assertEqual(self.runtime.active, OLD["generation_id"])
        self.assertEqual(self.runtime.binding, OLD)
        self.assertEqual(self.runtime.marker, IDENT)
        self.assertNotIn("resume", self.runtime.calls)
        self.flow.resume(IDENT)
        self.assertIsNone(self.runtime.marker)

    def test_rollback_requires_original_owner_and_verified_barrier(self):
        self.ready()
        with self.assertRaisesRegex(life.LifecycleError, "owned_by_other"):
            self.flow.rollback(OTHER)
        self.runtime.marker = None
        with self.assertRaisesRegex(life.LifecycleError, "maintenance"):
            self.flow.rollback(IDENT)

    def test_rollback_rejects_unrelated_runtime_without_stop(self):
        self.ready()
        self.runtime.binding = {**NEW, "image_id":"sha256:"+"f"*64}
        self.runtime.calls.clear()
        with self.assertRaisesRegex(life.LifecycleError, "unexpected_runtime"):
            self.flow.rollback(IDENT)
        self.assertNotIn("stop", self.runtime.calls)

    def test_rollback_failure_preserves_barrier_and_recovery(self):
        self.ready()
        self.runtime.fail = "restore"
        with self.assertRaises(TimeoutError):self.flow.rollback(IDENT)
        self.assertEqual(self.flow.status()["state"], "rolling_back")
        self.assertEqual(self.runtime.marker, IDENT)
        self.assertNotIn("resume", self.runtime.calls)

    def test_resume_rechecks_exact_container_identity(self):
        self.ready();self.runtime.ids["worker"] = "f"*64
        with self.assertRaisesRegex(life.LifecycleError, "identity_changed"):
            self.flow.resume(IDENT)
        self.assertNotIn("resume", self.runtime.calls)

    def test_resume_lost_reply_is_not_replayed_or_rolled_back(self):
        self.ready()
        self.runtime.fail = "resumed"
        with self.assertRaises(TimeoutError):self.flow.resume(IDENT)
        self.assertIsNone(self.runtime.marker)
        self.flow = self.create()
        self.assertEqual(self.flow.status()["state"], "resuming")
        for action in (self.flow.resume, self.flow.rollback):
            with self.assertRaisesRegex(life.LifecycleError, "reconciliation"):
                action(IDENT)

    def test_resume_commit_failure_remains_unknown_without_second_resume(self):
        self.ready()
        original = self.flow._save
        def save(row, phase):
            if phase == "complete":raise OSError("synthetic")
            original(row, phase)
        with patch.object(self.flow, "_save", side_effect=save):
            with self.assertRaises(OSError):self.flow.resume(IDENT)
        self.assertEqual(self.flow.status()["state"], "resuming")
        self.assertIsNone(self.runtime.marker)

    def test_foreign_resume_and_premature_resume_are_rejected(self):
        self.ready()
        with self.assertRaisesRegex(life.LifecycleError, "owned_by_other"):
            self.flow.resume(OTHER)
        row = self.flow._load();self.flow._save(row, "starting")
        with self.assertRaisesRegex(life.LifecycleError, "reconciliation"):
            self.flow.resume(IDENT)

    def test_status_contains_no_paths_secrets_or_unverified_success(self):
        self.runtime.fail = "start"
        with self.assertRaises(TimeoutError):self.ready()
        value = self.flow.status()
        self.assertEqual(set(value), {"request_id","state","generation_id",
                                     "dispatch_blocked","requires_recovery"})
        self.assertNotIn("synthetic secret", json.dumps(value))
        self.assertNotIn(str(self.root), json.dumps(value))

    def test_corrupt_and_duplicate_journal_are_not_adopted(self):
        for raw in (b"[]", b"bad", b"x"*65537, b'{"schema":1,"schema":1}'):
            self.flow.path.write_bytes(raw);self.flow.path.chmod(0o600)
            with self.subTest(raw=raw[:20]), self.assertRaises(life.LifecycleError):
                self.flow.status()

    def test_serialization_blocks_second_mutation(self):
        with life.storage._store_lock(self.root):
            with self.assertRaises(life.storage.ActivationError):
                self.ready()
        self.assertNotIn("pause", self.runtime.calls)

    @unittest.skipUnless(os.name == "posix", "POSIX state ownership")
    def test_unsafe_journal_permissions_and_links_rejected(self):
        self.ready();self.flow.path.chmod(0o644)
        with self.assertRaises(life.LifecycleError):self.flow.status()
        self.flow.path.chmod(0o600)
        os.link(self.flow.path, self.root/"alias")
        with self.assertRaises(life.LifecycleError):self.flow.status()
        (self.root/"alias").unlink();self.flow.path.unlink()
        self.flow.path.symlink_to(self.root/"missing")
        with self.assertRaises(life.LifecycleError):self.flow.status()

    @unittest.skipUnless(os.name == "posix", "POSIX lock ownership")
    def test_linked_lock_is_rejected_before_use(self):
        lock = self.root/"transactions/install.lock"
        lock.symlink_to(self.root/"external")
        with self.assertRaises(life.LifecycleError):self.create()

    def test_missing_adapter_is_not_a_deployable_default(self):
        with self.assertRaisesRegex(life.LifecycleError, "missing_runtime_adapter"):
            life.Lifecycle(self.root, object(), verify_volume=lambda:True,
                           active_generation=lambda:None, activate=lambda x:None,
                           restore=lambda x:None)


if __name__ == "__main__":unittest.main()
