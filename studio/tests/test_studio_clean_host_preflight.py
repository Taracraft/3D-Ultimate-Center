"""Synthetic clean-host exclusivity tests; no Docker or systemd mutation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Slicer-Server"))
import clean_host_preflight as preflight


class Runner:
    def __init__(self):
        self.unit = {}
        self.containers = []
        self.calls = []

    def __call__(self, argv, *, timeout):
        self.calls.append(argv)
        if argv[0] == "systemctl":
            unit = argv[-1]
            if unit in self.unit:
                return preflight.Result(0, (self.unit[unit] + "\nactive\n").encode(), b"")
            return preflight.Result(4, b"not-found\ninactive\n", b"")
        if argv[:3] == ("docker", "container", "ls"):
            body = b"".join(json.dumps(row).encode() + b"\n" for row in self.containers)
            return preflight.Result(0, body, b"")
        raise AssertionError(argv)


class CleanHostPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "root"
        self.proc = self.base / "proc"
        self.root.mkdir()
        self.proc.mkdir()
        self.runner = Runner()

    def make(self):
        return preflight.CleanHostPreflight(
            root=self.root, process_root=self.proc, runner=self.runner)

    def test_clean_host_is_accepted_read_only(self):
        with patch.object(preflight.sys, "platform", "linux"):
            self.assertTrue(self.make().require_clean())
        self.assertEqual(len(self.runner.calls), len(preflight.UNIT_NAMES) + 1)
        self.assertFalse(list(self.root.rglob("*")))

    def test_each_native_marker_blocks(self):
        for marker in preflight.MARKERS:
            with self.subTest(marker=marker):
                target = self.root / marker
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("marker")
                with patch.object(preflight.sys, "platform", "linux"):
                    with self.assertRaisesRegex(
                            preflight.HostExclusivityError, "native_slicer_present"):
                        self.make().require_clean()
                target.unlink()

    def test_loaded_native_unit_blocks(self):
        self.runner.unit[preflight.UNIT_NAMES[0]] = "loaded"
        with patch.object(preflight.sys, "platform", "linux"):
            with self.assertRaisesRegex(
                    preflight.HostExclusivityError, "native_slicer_present"):
                self.make().require_clean()

    def test_native_process_blocks_without_exposing_command(self):
        item = self.proc / "123"
        item.mkdir()
        (item / "cmdline").write_bytes(
            b"python3\0/opt/ultimate-slicer-server/server.py\0secret\0")
        with patch.object(preflight.sys, "platform", "linux"):
            with self.assertRaisesRegex(
                    preflight.HostExclusivityError, "native_slicer_present"):
                self.make().require_clean()

    def test_known_or_alternate_slicer_container_blocks(self):
        self.runner.containers = [{
            "Names": "old-runtime",
            "Image": "private/ultimate-slicer:test",
            "Labels": "com.docker.compose.project=foreign",
        }]
        with patch.object(preflight.sys, "platform", "linux"):
            with self.assertRaisesRegex(
                    preflight.HostExclusivityError, "container_slicer_present"):
                self.make().require_clean()

    def test_unavailable_inventory_fails_closed(self):
        def failed(argv, *, timeout):
            return preflight.Result(1, b"", b"unavailable")
        with patch.object(preflight.sys, "platform", "linux"):
            with self.assertRaisesRegex(
                    preflight.HostExclusivityError, "host_inventory_unknown"):
                preflight.CleanHostPreflight(
                    root=self.root, process_root=self.proc,
                    runner=failed).require_clean()

    def test_permission_denial_fails_closed(self):
        item = self.proc / "123"
        item.mkdir()
        with patch.object(Path, "read_bytes", side_effect=PermissionError("denied")):
            with patch.object(preflight.sys, "platform", "linux"):
                with self.assertRaisesRegex(
                        preflight.HostExclusivityError, "host_inventory_unknown"):
                    self.make().require_clean()

    def test_cli_reports_counts_without_inventory_details(self):
        with patch.object(preflight, "CleanHostPreflight") as factory:
            factory.return_value.inspect.return_value = {
                "schema": 1, "clean": False,
                "native_units": ["secret-unit"],
                "native_paths": ["secret-path"],
                "native_processes": ["123"],
                "slicer_containers": ["0"],
            }
            with patch("builtins.print") as emit:
                self.assertEqual(preflight.main(), 3)
        output = emit.call_args.args[0]
        self.assertNotIn("secret", output)
        self.assertIn('"native_units": 1', output)

    def test_non_linux_is_not_accepted_as_deployment_evidence(self):
        with patch.object(preflight.sys, "platform", "win32"):
            with self.assertRaisesRegex(
                    preflight.HostExclusivityError, "linux_host_required"):
                self.make().require_clean()


if __name__ == "__main__":
    unittest.main()
