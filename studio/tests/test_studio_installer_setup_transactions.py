"""Guided installer transaction regressions; temporary files and fake host only."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio"
PKG = "studio_installer_transaction_regressions"


def load(name):
    package = sys.modules.setdefault(PKG, type(sys)(PKG))
    package.__path__ = [str(COMPONENT)]
    full = PKG + "." + name
    spec = importlib.util.spec_from_file_location(full, COMPONENT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


backend = load("slicer_installer_backend")
setup = load("slicer_installer_setup")


class FakeClient:
    calls = []
    stage_entered = None
    stage_release = None

    def __init__(self, *args, **kwargs):
        pass

    def request(self, token, request):
        self.calls.append(request.copy())
        if request["operation"] == "stage" and self.stage_entered is not None:
            self.stage_entered.set()
            if not self.stage_release.wait(2):
                raise AssertionError("test stage was not released")
        return {"ok": True, "request_id": request.get("request_id", request.get("target")),
                "state": "prepared" if request["operation"] in ("stage", "retry") else "observed"}


class InstallerTransactionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        auth = self.base / "credential"
        auth.mkdir(mode=0o700)
        store = backend.InstallerCredentialStore(auth, expected_host_id="a" * 32, server_uid=0)
        backend._atomic_private_json(store.path, {"host_id": "a" * 32,
            "principal": "synthetic", "token": "T" * 64})
        self.backend = backend.InstallerBackend(store, self.base, server_uid=0,
                                               client_factory=FakeClient)
        self.state = self.base / "state"
        self.state.mkdir(mode=0o700)
        self.flow = setup.GuidedInstallerSetup(self.backend, self.state)
        FakeClient.calls = []
        FakeClient.stage_entered = FakeClient.stage_release = None

    def assert_status_targets(self, operation):
        self.flow.run(operation)
        target = FakeClient.calls[-1]["request_id"]
        self.flow.run("status")
        self.assertEqual(FakeClient.calls[-1]["target"], target)

    def test_status_after_initialize(self):
        self.assert_status_targets("initialize")

    def test_status_during_staging(self):
        self.assert_status_targets("stage")

    def test_status_after_retry(self):
        self.flow.run("stage")
        self.assert_status_targets("retry")

    def test_status_after_activation_retains_activation_target(self):
        self.flow.run("stage")
        self.assert_status_targets("activate")

    def test_rejected_activation_does_not_persist_phantom_request(self):
        before = self.flow.path.read_bytes()
        with self.assertRaises(setup.InstallerSetupError):
            self.flow.run("activate")
        self.assertEqual(self.flow.path.read_bytes(), before)
        self.assertEqual(FakeClient.calls, [])

    def test_rejected_retry_does_not_persist_phantom_request(self):
        before = self.flow.path.read_bytes()
        with self.assertRaises(setup.InstallerSetupError):
            self.flow.run("retry")
        self.assertEqual(self.flow.path.read_bytes(), before)

    def test_recovery_without_target_does_not_persist_phantom_request(self):
        before = self.flow.path.read_bytes()
        with self.assertRaises(setup.InstallerSetupError):
            self.flow.run("recover", target_action="activate", recovery_action="rollback")
        self.assertEqual(self.flow.path.read_bytes(), before)

    def test_boolean_schema_is_not_integer_schema(self):
        value = json.loads(self.flow.path.read_bytes())
        value["schema"] = True
        self.flow.path.write_bytes(json.dumps(value).encode())
        with self.assertRaises(setup.InstallerSetupError):
            self.flow.public_status()

    def test_nonfinite_saved_result_is_rejected(self):
        value = json.loads(self.flow.path.read_bytes())
        value["last_result"] = {"ok": True, "value": float("nan")}
        self.flow.path.write_bytes(json.dumps(value).encode())
        with self.assertRaises(setup.InstallerSetupError):
            self.flow.public_status()

    def test_hardlinked_state_is_rejected(self):
        other = self.base / "state-alias.json"
        try:
            os.link(self.flow.path, other)
        except OSError:
            self.skipTest("hardlinks not supported by temporary filesystem")
        with self.assertRaises(setup.InstallerSetupError):
            self.flow.public_status()

    def test_parallel_flows_preserve_single_operation_identity(self):
        others = [setup.GuidedInstallerSetup(self.backend, self.state) for _ in range(5)]
        barrier = threading.Barrier(len(others))
        original = setup.secrets.token_hex
        def delayed_token(n):
            time.sleep(0.025)
            return original(n)
        def run(flow):
            barrier.wait(timeout=2)
            return flow.run("initialize")
        with patch.object(setup.secrets, "token_hex", side_effect=delayed_token):
            with ThreadPoolExecutor(max_workers=len(others)) as pool:
                results = list(pool.map(run, others))
        ids = {x["request_id"] for x in FakeClient.calls if x["operation"] == "initialize"}
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids, {self.flow.public_status()["requests"]["initialize"]})
        self.assertTrue(all(x["ok"] for x in results))

    def test_cancel_does_not_wait_behind_blocking_stage_request(self):
        FakeClient.stage_entered = threading.Event()
        FakeClient.stage_release = threading.Event()
        other = setup.GuidedInstallerSetup(self.backend, self.state)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                stage = pool.submit(self.flow.run, "stage")
                self.assertTrue(FakeClient.stage_entered.wait(1))
                cancel = pool.submit(other.run, "cancel")
                try:
                    self.assertTrue(cancel.result(timeout=1)["ok"])
                finally:
                    FakeClient.stage_release.set()
                self.assertTrue(stage.result(timeout=1)["ok"])
        finally:
            FakeClient.stage_release.set()
            FakeClient.stage_entered = FakeClient.stage_release = None
        stage_id = next(x["request_id"] for x in FakeClient.calls if x["operation"] == "stage")
        self.assertEqual(next(x["target"] for x in FakeClient.calls if x["operation"] == "cancel"), stage_id)

    def test_invalid_action_type_has_stable_error(self):
        with self.assertRaises(setup.InstallerSetupError):
            self.flow.run([])


if __name__ == "__main__":
    unittest.main()
