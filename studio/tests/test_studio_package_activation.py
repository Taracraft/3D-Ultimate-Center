"""Synthetic persistent-store tests; no engine, service or container is started."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Slicer-Server"))
import engine_catalog as catalog
import package_activation as activation


def sha(data):
    return hashlib.sha256(data).hexdigest()


def release(engine, marker=b"one"):
    entry = catalog.ENTRYPOINTS[engine]
    files = [(entry, b"engine-" + marker, "engine", True),
             ("licenses/NOTICE", b"synthetic notice", "license", False)]
    if engine == "bambu_studio":
        files.append(("resources/profiles/base.json", b"{}", "profiles", False))
        files.append(("resources/data.bin", b"resource", "resources", False))
    elif engine == "prusaslicer":
        files.append(("resources/base.ini", b"[print]", "profiles", False))
        files.append(("lib/OCCTWrapper.so", b"module", "runtime", False))
        files.append(("resources/data.bin", b"resource", "resources", False))
    else:
        files.append(("resources/definitions/base.def.json", b"{}", "profiles", False))
        files.append(("resources/data.bin", b"resource", "resources", False))
    specs = tuple(catalog.FileSpec(path, sha(data), len(data), role, executable, path)
                  for path, data, role, executable in files)
    artifact = catalog.Artifact(
        engine + "_package", "1.0.0", "https://deb.debian.org/debian/pool/package.deb",
        "a" * 64, 1, "deb", "synthetic-test",
        activation_source(engine), "b" * 40, specs)
    return catalog.Release(engine, "1.0.0", "amd64", (artifact,)), dict(
        (path, data) for path, data, _, _ in files)


def activation_source(engine):
    if engine == "bambu_studio":
        return "https://github.com/bambulab/BambuStudio/tree/" + "b" * 40
    if engine == "prusaslicer":
        return "https://github.com/prusa3d/PrusaSlicer/tree/" + "b" * 40
    return "https://github.com/Ultimaker/CuraEngine/tree/" + "b" * 40


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        if os.name != "nt":
            self.base.chmod(0o700)
        self.store = self.base / "engine-store"
        self.identity = activation.initialize_store(self.store)
        self.counter = 0

    def candidates(self, marker=b"one"):
        self.counter += 1
        result = {}
        for engine in catalog.ENTRYPOINTS:
            item = self.base / ("candidate-" + engine + "-" + marker.decode("ascii")
                                + "-" + str(self.counter))
            payload = item / "payload" / engine
            payload.mkdir(parents=True)
            rel, files = release(engine, marker)
            for name, data in files.items():
                path = payload / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            if os.name != "nt":
                for path in payload.rglob("*"):
                    if path.is_dir():
                        path.chmod(0o755)
                for spec in rel.artifacts[0].files:
                    (payload / spec.path).chmod(0o755 if spec.executable else 0o644)
            receipt = {"schema": 1, "state": "prepared", "release": asdict(rel),
                       "engine_executed": False, "activated": False}
            (item / "READY.json").write_text(
                json.dumps(receipt, sort_keys=True, separators=(",", ":")),
                encoding="utf-8", newline="\n")
            result[engine] = item
        return result

    def activate(self, candidates=None, **kwargs):
        with patch.object(activation, "SPACE_MARGIN", 4096):
            return activation.activate_generation(
                self.store, self.identity["store_id"], candidates or self.candidates(),
                kwargs.pop("workers_stopped", lambda: True), **kwargs)

    def test_store_identity_and_layout(self):
        checked = activation.verify_store(self.store, self.identity["store_id"])
        self.assertEqual(checked, self.identity)
        self.assertEqual(set(p.name for p in self.store.iterdir()),
                         {"STORE.json", "generations", "transactions", "reservations"})
        with self.assertRaisesRegex(activation.ActivationError, "^wrong_store_identity$"):
            activation.verify_store(self.store, "0" * 32)

    def test_store_requires_empty_private_root(self):
        occupied = self.base / "occupied"
        occupied.mkdir()
        (occupied / "user-data").write_text("keep")
        with self.assertRaisesRegex(activation.ActivationError, "^store_not_empty$"):
            activation.initialize_store(occupied)
        self.assertEqual((occupied / "user-data").read_text(), "keep")
        if os.name != "nt":
            shared = self.base / "shared"
            shared.mkdir(mode=0o777)
            shared.chmod(0o777)
            with self.assertRaisesRegex(activation.ActivationError, "^store_permissions$"):
                activation.initialize_store(shared)

    def test_wrong_device_and_linked_layout_are_rejected(self):
        marker = json.loads((self.store / "STORE.json").read_text())
        marker["device"] += 1
        (self.store / "STORE.json").write_text(json.dumps(marker))
        with self.assertRaisesRegex(activation.ActivationError, "^wrong_store_device$"):
            activation.verify_store(self.store, self.identity["store_id"])

    def test_complete_generation_activates_atomically(self):
        candidates = self.candidates()
        before = {engine: sorted((path / "payload" / engine).rglob("*"))
                  for engine, path in candidates.items()}
        result = self.activate(candidates)
        self.assertTrue(result["activated"])
        self.assertIsNone(result["previous_generation_id"])
        active = activation.active_generation(self.store, self.identity["store_id"])
        self.assertEqual(active["generation_id"], result["generation_id"])
        self.assertEqual({r["engine"] for r in active["releases"]}, set(catalog.ENTRYPOINTS))
        self.assertFalse((self.store / "ACTIVE.json").is_symlink())
        self.assertEqual(list((self.store / "reservations").iterdir()), [])
        for engine, path in candidates.items():
            self.assertTrue((path / "READY.json").is_file())
            self.assertEqual(before[engine], sorted((path / "payload" / engine).rglob("*")))

    def test_all_three_engines_are_required(self):
        candidates = self.candidates()
        candidates.pop("curaengine")
        with self.assertRaisesRegex(activation.ActivationError, "^incomplete_generation$"):
            self.activate(candidates)
        self.assertFalse((self.store / "ACTIVE.json").exists())

    def test_worker_acknowledgement_is_fail_closed(self):
        with self.assertRaisesRegex(activation.ActivationError, "^workers_not_stopped$"):
            self.activate(workers_stopped=lambda: False)
        self.assertFalse((self.store / "ACTIVE.json").exists())
        states = [json.loads(p.read_text())["state"]
                  for p in (self.store / "transactions").glob("t-*.json")]
        self.assertEqual(states, ["failed"])

    def test_manifest_is_rechecked_after_worker_stop(self):
        candidates = self.candidates()
        def stop_and_tamper():
            generation = next(p for p in (self.store / "generations").iterdir()
                              if p.name.startswith("g-"))
            (generation / "curaengine/bin/CuraEngine").write_bytes(b"tampered")
            return True
        with self.assertRaisesRegex(activation.ActivationError, "^manifest_mismatch$"):
            self.activate(candidates, workers_stopped=stop_and_tamper)
        self.assertFalse((self.store / "ACTIVE.json").exists())

    def test_candidate_extra_missing_and_symlink_are_rejected(self):
        candidates = self.candidates()
        (candidates["curaengine"] / "payload/curaengine/extra").write_text("x")
        with self.assertRaisesRegex(activation.ActivationError, "^manifest_mismatch$"):
            self.activate(candidates)
        shutil.rmtree(candidates["curaengine"])
        candidates = self.candidates(b"two")
        (candidates["curaengine"] / "payload/curaengine/bin/CuraEngine").unlink()
        with self.assertRaisesRegex(activation.ActivationError, "^manifest_mismatch$"):
            self.activate(candidates)
        if hasattr(os, "symlink"):
            candidates = self.candidates(b"tri")
            target = candidates["curaengine"] / "payload/curaengine/resources/data.bin"
            target.unlink()
            try:
                target.symlink_to(candidates["curaengine"] / "READY.json")
            except OSError:
                return
            with self.assertRaisesRegex(activation.ActivationError, "^linked_generation_path$"):
                self.activate(candidates)

    def test_insufficient_space_never_creates_generation(self):
        usage = shutil.disk_usage(self.store)
        with patch.object(activation.shutil, "disk_usage",
                          return_value=type(usage)(usage.total, usage.used, 1)), \
             patch.object(activation, "SPACE_MARGIN", 4096), \
             self.assertRaisesRegex(activation.ActivationError, "^insufficient_space$"):
            activation.activate_generation(
                self.store, self.identity["store_id"], self.candidates(), lambda: True)
        self.assertFalse((self.store / "ACTIVE.json").exists())
        self.assertEqual(list((self.store / "reservations").iterdir()), [])

    def test_cancellation_is_retryable_and_preserves_candidate(self):
        candidates = self.candidates()
        with self.assertRaisesRegex(activation.ActivationError, "^cancelled$"):
            self.activate(candidates, cancelled=lambda: True)
        self.assertTrue(all((p / "READY.json").is_file() for p in candidates.values()))
        self.assertTrue(self.activate(candidates)["activated"])

    def test_installer_lock_serializes_processes(self):
        with activation._store_lock(self.store):
            with self.assertRaisesRegex(activation.ActivationError, "^installer_busy$"):
                self.activate()

    def test_old_generation_and_unrelated_data_survive_upgrade(self):
        first = self.activate(self.candidates(b"one"))
        user_data = self.store / "user-data"
        user_data.mkdir()
        (user_data / "profile.json").write_text("keep")
        second = self.activate(self.candidates(b"two"))
        self.assertNotEqual(first["generation_id"], second["generation_id"])
        self.assertEqual(second["previous_generation_id"], first["generation_id"])
        self.assertTrue((self.store / "generations" / first["generation_id"]).is_dir())
        self.assertEqual((user_data / "profile.json").read_text(), "keep")

    def test_orphan_before_switch_must_be_resolved(self):
        transaction_id = "t-" + "1" * 32
        state = {"schema": 1, "transaction_id": transaction_id, "state": "ready",
                 "generation_id": "g-" + "2" * 64, "previous_generation_id": None}
        activation._atomic_json(activation._transaction_path(self.store, transaction_id), state)
        with self.assertRaisesRegex(activation.ActivationError, "^orphaned_transaction$"):
            self.activate()
        recovered = activation.recover_transaction(
            self.store, self.identity["store_id"], transaction_id, "abort")
        self.assertEqual(recovered["state"], "aborted")
        self.assertIsNone(recovered["generation_id"])
        self.assertTrue(self.activate()["activated"])

    def test_crash_after_switch_can_be_adopted(self):
        original = activation._atomic_json
        crashed = {"done": False}
        def fail_final(path, value):
            if (not crashed["done"] and path.parent.name == "transactions"
                    and value.get("state") == "activated"):
                crashed["done"] = True
                raise OSError("synthetic crash")
            return original(path, value)
        with patch.object(activation, "_atomic_json", side_effect=fail_final), \
             self.assertRaisesRegex(activation.ActivationError, "^activation_failed$"):
            self.activate()
        orphan = next(json.loads(p.read_text()) for p in
                      (self.store / "transactions").glob("t-*.json"))
        self.assertEqual(orphan["state"], "activating")
        recovered = activation.recover_transaction(
            self.store, self.identity["store_id"], orphan["transaction_id"],
            "adopt", lambda: True)
        self.assertEqual(recovered["state"], "adopted")
        self.assertEqual(recovered["generation_id"], orphan["generation_id"])

    def test_crash_after_upgrade_can_roll_back(self):
        first = self.activate(self.candidates(b"one"))
        original = activation._atomic_json
        crashed = {"done": False}
        def fail_final(path, value):
            if (not crashed["done"] and path.parent.name == "transactions"
                    and value.get("state") == "activated"):
                crashed["done"] = True
                raise OSError("synthetic crash")
            return original(path, value)
        with patch.object(activation, "_atomic_json", side_effect=fail_final), \
             self.assertRaisesRegex(activation.ActivationError, "^activation_failed$"):
            self.activate(self.candidates(b"two"))
        orphan = [json.loads(p.read_text()) for p in
                  (self.store / "transactions").glob("t-*.json")
                  if json.loads(p.read_text())["state"] == "activating"][0]
        recovered = activation.recover_transaction(
            self.store, self.identity["store_id"], orphan["transaction_id"],
            "rollback", lambda: True)
        self.assertEqual(recovered["state"], "rolled_back")
        self.assertEqual(recovered["generation_id"], first["generation_id"])
        self.assertTrue((self.store / "generations" / orphan["generation_id"]).is_dir())

    def test_generation_corruption_blocks_read_and_rollback(self):
        first = self.activate(self.candidates())
        target = self.store / "generations" / first["generation_id"] / "prusaslicer/lib/OCCTWrapper.so"
        target.write_bytes(b"changed")
        with self.assertRaisesRegex(activation.ActivationError, "^manifest_mismatch$"):
            activation.active_generation(self.store, self.identity["store_id"])

    def test_posix_modes_are_enforced(self):
        if os.name == "nt":
            self.skipTest("POSIX ownership/mode contract")
        candidates = self.candidates()
        path = candidates["curaengine"] / "payload/curaengine/resources/data.bin"
        path.chmod(0o666)
        with self.assertRaisesRegex(activation.ActivationError, "^manifest_mode_mismatch$"):
            self.activate(candidates)



    def test_first_install_restore_removes_only_active_and_is_idempotent(self):
        ident = "c" * 32
        result = self.activate(transaction_id="t-" + ident)
        generation = result["generation_id"]
        restored = activation.restore_first_install_absence(
            self.store, self.identity["store_id"], "t-" + ident, generation, lambda: True)
        self.assertEqual(restored, {"transaction_id": "t-" + ident,
                                   "state": "first_active_absent",
                                   "generation_id": None})
        self.assertIsNone(activation.active_generation(self.store, self.identity["store_id"]))
        self.assertTrue((self.store / "generations" / generation).is_dir())
        self.assertEqual(activation.restore_first_install_absence(
            self.store, self.identity["store_id"], "t-" + ident,
            generation, lambda: True), restored)

    def test_first_install_restore_rejects_running_or_wrong_binding(self):
        ident = "d" * 32
        result = self.activate(transaction_id="t-" + ident)
        generation = result["generation_id"]
        with self.assertRaisesRegex(activation.ActivationError, "^workers_not_stopped$"):
            activation.restore_first_install_absence(
                self.store, self.identity["store_id"], "t-" + ident,
                generation, lambda: False)
        self.assertEqual(activation.active_generation(
            self.store, self.identity["store_id"])["generation_id"], generation)
        with self.assertRaisesRegex(activation.ActivationError,
                                    "^first_install_restore_binding_mismatch$"):
            activation.restore_first_install_absence(
                self.store, self.identity["store_id"], "t-" + "e" * 32,
                generation, lambda: True)

    def test_first_install_restore_recovers_lost_final_receipt(self):
        ident = "f" * 32
        result = self.activate(transaction_id="t-" + ident)
        generation = result["generation_id"]
        original = activation._atomic_json
        def lost(path, value):
            original(path, value)
            if value.get("state") == "first_active_absent":
                raise OSError("synthetic lost final receipt")
        with patch.object(activation, "_atomic_json", side_effect=lost), self.assertRaises(OSError):
            activation.restore_first_install_absence(
                self.store, self.identity["store_id"], "t-" + ident,
                generation, lambda: True)
        self.assertIsNone(activation.active_generation(self.store, self.identity["store_id"]))
        self.assertEqual(activation.restore_first_install_absence(
            self.store, self.identity["store_id"], "t-" + ident,
            generation, lambda: True)["state"], "first_active_absent")


if __name__ == "__main__":
    unittest.main()
