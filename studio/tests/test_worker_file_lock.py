"""Portable lock ownership on empty files, never production job state."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

WORKER = Path(__file__).resolve().parents[1] / "deploy/homeassistant/host/3d-printer-slicing-server"
spec = importlib.util.spec_from_file_location("studio_file_lock_contract", WORKER / "job_control.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@contextmanager
def raw_lock(path):
    # An empty lock is valid for both OS APIs; no application initialization.
    with path.open("a+b", buffering=0) as handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


class FileLockOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.lock"

    def test_empty_locked_file_reports_busy_without_initialization_write(self):
        with raw_lock(self.path):
            with self.assertRaises(BlockingIOError):
                with module.file_lock(self.path, nonblocking=True):
                    self.fail("entered another owner's protected region")
        self.assertEqual(self.path.read_bytes(), b"")

    def test_blocking_contender_waits_for_empty_file_owner(self):
        attempted = threading.Event()
        entered = threading.Event()
        def contender():
            attempted.set()
            with module.file_lock(self.path):
                entered.set()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with raw_lock(self.path):
                future = pool.submit(contender)
                self.assertTrue(attempted.wait(2))
                self.assertFalse(entered.wait(.2))
                self.assertFalse(future.done())
            future.result(timeout=3)
        self.assertTrue(entered.is_set())
        self.assertEqual(self.path.read_bytes(), b"")

    def test_exception_releases_lock_without_changing_existing_bytes(self):
        self.path.write_bytes(b"existing-lock-content")
        with self.assertRaisesRegex(RuntimeError, "test-only"):
            with module.file_lock(self.path):
                raise RuntimeError("test-only")
        with module.file_lock(self.path, nonblocking=True):
            pass
        self.assertEqual(self.path.read_bytes(), b"existing-lock-content")

    def test_separate_process_cannot_enter_empty_file_owned_elsewhere(self):
        script = (
            "import importlib.util,sys\n"
            "from pathlib import Path\n"
            "spec=importlib.util.spec_from_file_location('child_lock',sys.argv[1])\n"
            "module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)\n"
            "try:\n"
            "    with module.file_lock(Path(sys.argv[2]),nonblocking=True):\n"
            "        print('unexpected-acquisition');sys.exit(3)\n"
            "except BlockingIOError:\n"
            "    print('busy')\n"
        )
        with raw_lock(self.path):
            result = subprocess.run(
                [sys.executable, "-c", script, str(WORKER / "job_control.py"), str(self.path)],
                capture_output=True, text=True, timeout=5,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "busy")
        self.assertEqual(self.path.read_bytes(), b"")
        with module.file_lock(self.path, nonblocking=True):
            pass

    def test_concurrent_first_acquisition_serializes_shared_state(self):
        workers = 8
        rounds = 20
        ready = threading.Barrier(workers)
        state = {"value": 0}
        def update():
            ready.wait(timeout=5)
            for _ in range(rounds):
                with module.file_lock(self.path):
                    value = state["value"]
                    # Event wait releases the GIL inside the critical section.
                    threading.Event().wait(.001)
                    state["value"] = value + 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(update) for _ in range(workers)]
            for future in futures:
                future.result(timeout=12)
        self.assertEqual(state["value"], workers * rounds)
        self.assertEqual(self.path.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
