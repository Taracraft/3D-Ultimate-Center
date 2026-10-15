"""Synthetic maintenance/dispatch acceptance; no engine or Docker invocation."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "deploy/homeassistant/host/3d-printer-slicing-server"
spec = importlib.util.spec_from_file_location("maintenance_job_control", HOST / "job_control.py")
jc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jc)
sys.path.insert(0, str(ROOT / "Slicer-Server"))
import container_service as service

IDENT = "a" * 32
OTHER = "b" * 32


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.control = jc.JobControl(self.base)
        self.marker = self.control.run / "container-maintenance.json"

    def test_begin_resume_durable_owner_and_no_service_stop_claim(self):
        first = self.control.begin_maintenance(IDENT)
        self.assertEqual(first["state"], "maintenance")
        self.assertFalse(first["services_stopped"])
        self.control = jc.JobControl(self.base)
        self.assertEqual(first, self.control.begin_maintenance(IDENT))
        self.assertEqual(self.control.end_maintenance(IDENT)["state"], "resumed")
        self.assertFalse(self.control.maintenance_pending())

    def test_other_request_cannot_adopt_or_resume(self):
        self.control.begin_maintenance(IDENT)
        before = self.marker.read_bytes()
        for call in (self.control.begin_maintenance, self.control.end_maintenance):
            with self.assertRaisesRegex(ValueError, "owned_by_other"):
                call(OTHER)
        self.assertEqual(self.marker.read_bytes(), before)

    def test_identifier_is_validated_before_writes(self):
        for ident in (None, True, "", "../escape", "a" * 31, "G" * 32):
            with self.subTest(ident=ident):
                with self.assertRaisesRegex(ValueError, "invalid_maintenance_id"):
                    self.control.begin_maintenance(ident)
        self.assertFalse(self.marker.exists())

    def test_queued_jobs_and_artifacts_are_preserved(self):
        queued = self.control.jobs / "example.queued.json"
        jc.atomic_json(queued, {"job_id": "example", "manual_release": True})
        out = self.control.output / "retained.bin"
        out.write_bytes(b"retained")
        before = queued.read_bytes()
        self.control.begin_maintenance(IDENT)
        self.control.end_maintenance(IDENT)
        self.assertEqual(queued.read_bytes(), before)
        self.assertEqual(out.read_bytes(), b"retained")

    def test_active_job_prevents_begin_without_modifying_job(self):
        job = self.control.jobs / "example.slicing.json"
        job.write_bytes(b"retained")
        with self.assertRaisesRegex(ValueError, "active_job"):
            self.control.begin_maintenance(IDENT)
        self.assertFalse(self.marker.exists())
        self.assertEqual(job.read_bytes(), b"retained")

    def test_recovery_latch_blocks_begin_and_resume(self):
        recovery = self.control.run / "container-recovery.json"
        recovery.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "worker_recovery"):
            self.control.begin_maintenance(IDENT)
        recovery.unlink()
        self.control.begin_maintenance(IDENT)
        recovery.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "worker_recovery"):
            self.control.end_maintenance(IDENT)
        self.assertTrue(self.marker.exists())

    def test_new_orphan_blocks_resume(self):
        self.control.begin_maintenance(IDENT)
        (self.control.jobs / "example.slicing.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "worker_recovery"):
            self.control.end_maintenance(IDENT)
        self.assertTrue(self.marker.exists())

    def test_missing_resume_is_unknown_not_forged_success(self):
        with self.assertRaisesRegex(ValueError, "maintenance_not_present"):
            self.control.end_maintenance(IDENT)

    def test_malformed_marker_never_adopted_or_removed(self):
        for raw in (b"[]", b"invalid", b"x" * 4097,
                    b'{"schema":true,"state":"maintenance","request_id":"' + IDENT.encode() + b'"}',
                    b'{"schema":1,"schema":1,"state":"maintenance","request_id":"' + IDENT.encode() + b'"}'):
            self.marker.write_bytes(raw)
            self.marker.chmod(0o600)
            with self.subTest(raw=raw[:30]):
                for call in (self.control.begin_maintenance, self.control.end_maintenance):
                    with self.assertRaises(ValueError):
                        call(IDENT)
                self.assertTrue(self.control.maintenance_pending())
                self.assertEqual(self.marker.read_bytes(), raw)

    def test_fsync_failure_retains_barrier_and_can_be_reconciled(self):
        with patch.object(self.control, "_sync_run", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                self.control.begin_maintenance(IDENT)
        self.assertTrue(self.control.maintenance_pending())
        self.assertEqual(self.control.begin_maintenance(IDENT)["state"], "maintenance")

    def test_resume_fsync_failure_does_not_claim_success(self):
        self.control.begin_maintenance(IDENT)
        with patch.object(self.control, "_sync_run", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                self.control.end_maintenance(IDENT)
        self.assertFalse(self.control.maintenance_pending())
        with self.assertRaisesRegex(ValueError, "maintenance_not_present"):
            self.control.end_maintenance(IDENT)

    def test_busy_dispatcher_never_stopped_or_signalled(self):
        with jc.file_lock(self.control.run / "dispatcher.guard", nonblocking=True):
            with self.assertRaises(BlockingIOError):
                self.control.begin_maintenance(IDENT)
        self.assertFalse(self.marker.exists())

    @unittest.skipUnless(os.name == "posix", "Linux dispatcher")
    def test_dispatch_never_claims_or_executes_during_maintenance(self):
        self.control.begin_maintenance(IDENT)
        with patch.object(self.control, "_claim", side_effect=AssertionError("must not claim")), \
             patch.object(jc.subprocess, "Popen", side_effect=AssertionError("must not execute")):
            self.assertEqual(self.control.dispatch(Path("/nonexistent")), {"status": "maintenance"})

    @unittest.skipUnless(os.name == "posix", "Linux dispatcher")
    def test_dispatch_and_begin_share_one_lock(self):
        entered, release = threading.Event(), threading.Event()
        result = {}
        def claim():
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            return None
        def dispatch():
            result.update(self.control.dispatch(Path("/nonexistent")))
        with patch.object(self.control, "_claim", side_effect=claim):
            thread = threading.Thread(target=dispatch)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(BlockingIOError):
                    self.control.begin_maintenance(IDENT)
                self.assertFalse(self.marker.exists())
            finally:
                release.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, {"status": "idle"})
        self.control.begin_maintenance(IDENT)
        self.assertEqual(self.control.dispatch(Path("/nonexistent")), {"status": "maintenance"})

    @unittest.skipUnless(os.name == "posix", "POSIX modes and special files")
    def test_unsafe_modes_links_fifo_are_fail_closed(self):
        self.control.begin_maintenance(IDENT)
        self.marker.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            self.control.end_maintenance(IDENT)
        self.marker.unlink()
        self.marker.symlink_to(self.base / "missing")
        self.assertTrue(self.control.maintenance_pending())
        self.assertEqual(self.control.dispatch(Path("/nonexistent")), {"status": "maintenance"})
        with self.assertRaises(ValueError):
            self.control.begin_maintenance(IDENT)
        self.marker.unlink()
        os.mkfifo(self.marker)
        with self.assertRaises(ValueError):
            self.control.begin_maintenance(IDENT)

    @unittest.skipUnless(os.name == "posix", "POSIX hard links")
    def test_hardlinked_marker_is_rejected(self):
        self.control.begin_maintenance(IDENT)
        os.link(self.marker, self.base / "alias")
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            self.control.end_maintenance(IDENT)

    def test_worker_accepts_paused_dispatch_without_recovery(self):
        self.assertFalse(service.terminal_requires_recovery({"status": "maintenance"}))
        self.assertTrue(service.terminal_requires_recovery(
            {"status": "maintenance", "requires_recovery": True}))

    def test_trusted_container_commands_validate_data_and_do_not_run_worker(self):
        self.base.chmod(0o700)
        # Use a fresh runtime tree, not the JobControl-only fixture.
        runtime = self.base / "runtime"
        runtime.mkdir(mode=0o700)
        service.initialize_data(runtime)
        with patch.object(service, "canonical", return_value=jc), \
             patch.object(service, "configure_environment", side_effect=AssertionError("not runtime")), \
             patch.object(service, "emit") as emit:
            with patch.object(sys, "argv", ["service", "maintenance-begin", "--base", str(runtime),
                                            "--request-id", IDENT]):
                service.main()
            self.assertTrue(emit.call_args.kwargs["dispatch_blocked"])
            with patch.object(sys, "argv", ["service", "maintenance-status", "--base", str(runtime)]):
                service.main()
            self.assertTrue(emit.call_args.kwargs["dispatch_blocked"])
            with patch.object(sys, "argv", ["service", "maintenance-end", "--base", str(runtime),
                                            "--request-id", IDENT]):
                service.main()
            self.assertFalse(emit.call_args.kwargs["dispatch_blocked"])

    def test_command_rejects_foreign_data_without_initialization(self):
        runtime = self.base / "foreign"
        runtime.mkdir()
        original = runtime / "keep"
        original.write_bytes(b"user data")
        with patch.object(sys, "argv", ["service", "maintenance-begin", "--base", str(runtime),
                                        "--request-id", IDENT]):
            with self.assertRaises(ValueError):
                service.main()
        self.assertEqual(original.read_bytes(), b"user data")
        self.assertEqual(list(runtime.iterdir()), [original])


    @unittest.skipUnless(os.name == "posix" and getattr(os, "geteuid", lambda: -1)() == 0,
                         "Linux root required to verify actual runtime UID")
    def test_runtime_uid_can_initialize_pause_and_resume(self):
        import subprocess
        self.base.chmod(0o755)
        runtime = self.base / "unprivileged"
        runtime.mkdir(mode=0o700)
        os.chown(runtime, 65532, 65532)
        code = """
import os,sys,importlib.util,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import container_service as service
spec=importlib.util.spec_from_file_location('runtime_job',sys.argv[2])
jc=importlib.util.module_from_spec(spec)
spec.loader.exec_module(jc)
base=Path(sys.argv[3])
os.setgroups([])
os.setgid(65532)
os.setuid(65532)
service.initialize_data(base)
control=jc.JobControl(base)
result=control.begin_maintenance('a'*32)
assert result['dispatch_blocked'] is True
assert control.dispatch(Path('/nonexistent'))=={'status':'maintenance'}
control.end_maintenance('a'*32)
assert not control.maintenance_pending()
print(json.dumps({'uid':os.geteuid(),'passed':True}))
"""
        result = subprocess.run([sys.executable, "-c", code, str(ROOT / "Slicer-Server"),
                                 str(HOST / "job_control.py"), str(runtime)],
                                capture_output=True, text=True, timeout=15, check=True)
        self.assertEqual(json.loads(result.stdout), {"uid": 65532, "passed": True})


    def _initialize_for_test(self, base=None, request_id=None):
        target = (getattr(self, "_init_target", self.base / "initialized")
                  if base is None else base)
        if base is None and not hasattr(self, "_init_target"):
            target.mkdir()
            self._init_target = target
        with patch.object(service, "canonical", return_value=jc):
            result = service.initialize_data(target, maintenance_request_id=request_id)
        if base is None and self.control.base != target:
            self.base = target
            self.control = jc.JobControl(target)
            self.marker = self.control.run / "container-maintenance.json"
        return result

    def test_first_install_initialization_persists_canonical_dispatch_barrier(self):
        result = self._initialize_for_test(request_id=IDENT)
        self.assertEqual(result, {"initialized": True, "state": "ready",
                                  "dispatch_blocked": True})
        self.control = jc.JobControl(self.base)
        self.assertTrue(self.control.maintenance_pending())
        self.assertEqual(self.control._maintenance_record()["request_id"], IDENT)
        queued = self.control.jobs / "queued.queued.json"
        queued.write_text('{"manual_release":true}')
        self.assertTrue(self.control.maintenance_pending())
        self.assertTrue(queued.exists())
        self.assertEqual(list(self.control.jobs.glob("*.slicing.json")), [])

    def test_first_install_initialization_retry_same_id_is_idempotent(self):
        self._initialize_for_test(request_id=IDENT)
        before = self.marker.read_bytes()
        result = self._initialize_for_test(request_id=IDENT)
        self.assertEqual(result["initialized"], False)
        self.assertTrue(result["dispatch_blocked"])
        self.assertEqual(self.marker.read_bytes(), before)

    def test_first_install_different_owner_and_invalid_id_never_replace_barrier(self):
        self._initialize_for_test(request_id=IDENT)
        before = self.marker.read_bytes()
        with self.assertRaisesRegex(ValueError, "owned_by_other"):
            self._initialize_for_test(request_id=OTHER)
        self.assertEqual(self.marker.read_bytes(), before)
        other = self.base / "other"
        other.mkdir()
        with self.assertRaisesRegex(ValueError, "invalid_maintenance_id"):
            self._initialize_for_test(other, "../bad")
        self.assertEqual(list(other.iterdir()), [])

    def test_first_install_barrier_rejects_active_slicing_record_without_claiming_it(self):
        runtime = self.base / "runtime"
        runtime.mkdir()
        service.initialize_data(runtime)
        control = jc.JobControl(runtime)
        active = control.jobs / "existing.slicing.json"
        active.write_bytes(b"retained")
        with patch.object(service, "canonical", return_value=jc):
            with self.assertRaisesRegex(ValueError, "active_job"):
                service.initialize_data(runtime, maintenance_request_id=IDENT)
        self.assertFalse((control.run / "container-maintenance.json").exists())
        self.assertEqual(active.read_bytes(), b"retained")
        self.assertEqual(service.persistent_data(runtime), runtime)

    def test_data_init_cli_uses_only_local_bootstrap_environment(self):
        runtime = self.base / "cli-runtime"
        runtime.mkdir()
        with patch.dict(os.environ, {"STUDIO_BOOTSTRAP_REQUEST_ID": IDENT}):
            with patch.object(sys, "argv", ["service", "init-data", "--base", str(runtime)]), \
                    patch.object(service, "canonical", return_value=jc), \
                    patch.object(service, "emit") as emit:
                service.main()
        control = jc.JobControl(runtime)
        self.assertTrue(emit.call_args.kwargs["dispatch_blocked"])
        self.assertEqual(control._maintenance_record()["request_id"], IDENT)


if __name__ == "__main__":
    unittest.main()
