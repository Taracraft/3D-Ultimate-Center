"""Durability ordering at the data initialization commit boundary.

These tests model persisted directory entries; they do not simulate hardware
power loss or start any container, service, engine or job.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("data_durability_service", ROOT / "Slicer-Server/container_service.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class DataDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="studio-durability-")
        self.base = Path(self.temporary.name) / "data-volume"
        self.base.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def test_ready_requires_every_directory_entry_synced(self):
        persisted = {}
        original_sync = service._data_sync
        original_write = service._profile_write
        ready_checked = []
        def sync(directory):
            original_sync(directory)
            persisted[directory] = {p.name for p in directory.iterdir()}
        def write(path, raw):
            if path.name == ".data-ready.tmp":
                # Every newly created directory must already occur in the
                # persisted contents of its parent before committing ready.
                for relative in service.DATA_LAYOUT:
                    directory = self.base / relative
                    self.assertIn(directory.name, persisted.get(directory.parent, set()),
                                  str(directory.relative_to(self.base)))
                ready_checked.append(True)
            original_write(path, raw)
        with patch.object(service, "_data_sync", sync), patch.object(service, "_profile_write", write):
            service.initialize_data(self.base)
        self.assertEqual(ready_checked, [True])
        self.assertEqual(service.persistent_data(self.base), self.base)

    def test_parent_sync_failure_retains_preparing_and_blocks_retry(self):
        original_sync = service._data_sync
        def fail(directory):
            if directory == self.base / "data" and (directory / "jobs").is_dir():
                raise OSError("synthetic parent flush failure")
            original_sync(directory)
        with patch.object(service, "_data_sync", fail):
            with self.assertRaisesRegex(OSError, "synthetic parent"):
                service.initialize_data(self.base)
        receipt = self.base / "DATA_STATE.json"
        before = receipt.read_bytes()
        self.assertEqual(json.loads(before)["state"], "preparing")
        self.assertFalse((self.base / ".data-ready.tmp").exists())
        with self.assertRaisesRegex(ValueError, "data_recovery_required"):
            service.initialize_data(self.base)
        self.assertEqual(receipt.read_bytes(), before)

    def test_repeat_preserves_user_data_without_new_initialization(self):
        self.assertTrue(service.initialize_data(self.base)["initialized"])
        path = self.base / "data/jobs/fixture.json"
        path.write_bytes(b'{"synthetic":"retained"}')
        receipt = (self.base / "DATA_STATE.json").read_bytes()
        with patch.object(service, "_data_sync", side_effect=AssertionError("unexpected initialization")):
            self.assertFalse(service.initialize_data(self.base)["initialized"])
        self.assertEqual(path.read_bytes(), b'{"synthetic":"retained"}')
        self.assertEqual((self.base / "DATA_STATE.json").read_bytes(), receipt)


if __name__ == "__main__":
    unittest.main()
