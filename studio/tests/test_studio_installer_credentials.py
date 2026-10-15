"""Live credential snapshots with synthetic state; no listener or real service."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Slicer-Server"))
import restricted_installer as core

OLD = "a" * 64
NEW = "b" * 64


def credential(token, principal="homeassistant", scopes=core.SCOPES):
    return core.Credential(principal, hashlib.sha256(token.encode()).digest(), scopes)


class CredentialSnapshotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        control = base / "control"
        control.mkdir(mode=0o700)
        volume = base / "volume"
        volume.mkdir(mode=0o700)
        self.policy = core.HostPolicy("linux", "amd64", "managed_docker",
                                     True, True, volume / "engines", control)
        self.catalog = json.dumps({"schema": 1, "releases": [],
                                  "pending": sorted(core.catalog.ENTRYPOINTS)}).encode()
        self.snapshot = (credential(OLD),)
        self.calls = 0
        self.service = self.make()

    def provider(self):
        self.calls += 1
        if isinstance(self.snapshot, Exception):
            raise self.snapshot
        return self.snapshot

    def make(self, credentials=(), provider=True):
        return core.Installer(self.policy, credentials, self.catalog,
                              verify_volume=lambda: True, workers_stopped=lambda: True,
                              credential_provider=self.provider if provider else None)

    def call(self, token=OLD, operation="preflight", **fields):
        body = json.dumps({"protocol": 1, "operation": operation, **fields}).encode()
        return self.service.dispatch("Bearer " + token, body, secure_channel=True)

    def test_rotation_invalidates_old_token_without_restart(self):
        self.assertTrue(self.call()["ok"])
        self.snapshot = (credential(NEW),)
        self.assertEqual(self.call()["error"], "authentication_failed")
        self.assertTrue(self.call(NEW)["ok"])

    def test_revoke_all_denies_next_request(self):
        self.snapshot = ()
        self.assertEqual(self.call()["error"], "authentication_failed")
        self.assertEqual(self.call(NEW)["error"], "authentication_failed")

    def test_rotation_preserves_record_ownership_and_replay(self):
        ident = "1" * 32
        first = self.call(operation="initialize", request_id=ident)
        self.assertTrue(first["ok"], first)
        self.snapshot = (credential(NEW),)
        self.assertEqual(self.call(NEW, "initialize", request_id=ident), first)
        self.assertEqual(self.call(NEW, "status", target=ident)["state"], "initialized")
        self.snapshot = (credential(NEW, principal="another"),)
        self.assertEqual(self.call(NEW, "status", target=ident)["error"], "forbidden")

    def test_scope_reduction_takes_effect(self):
        self.snapshot = (credential(OLD, scopes=frozenset(("inspect",))),)
        self.assertTrue(self.call()["ok"])
        self.assertEqual(self.call(operation="initialize", request_id="2" * 32)["error"],
                         "forbidden")
        self.assertFalse(self.policy.store.exists())

    def test_provider_failure_never_uses_old_snapshot_or_leaks_details(self):
        self.assertTrue(self.call()["ok"])
        self.snapshot = OSError("private token and storage details")
        self.assertEqual(self.call(), {"ok": False, "error": "credentials_unavailable"})

    def test_invalid_snapshots_fail_closed(self):
        invalid = [
            [credential(OLD)], iter((credential(OLD),)), None,
            (credential(OLD), credential(NEW)),
            (credential(OLD), credential(OLD, principal="another")),
            (core.Credential("BAD", b"x" * 32, core.SCOPES),),
            tuple(credential(OLD, principal="p" + str(i)) for i in range(129)),
            (credential(OLD, scopes=frozenset(("shell",))),),
        ]
        for value in invalid:
            with self.subTest(kind=type(value).__name__):
                self.snapshot = value
                self.assertEqual(self.call()["error"], "credentials_unavailable")

    def test_provider_called_once_per_authenticated_request(self):
        before = self.calls
        self.assertTrue(self.call()["ok"])
        self.assertEqual(self.calls, before + 1)

    def test_insecure_or_malformed_headers_do_not_read_provider(self):
        before = self.calls
        for header, secure in [("Bearer " + OLD, False), ("invalid", True)]:
            self.assertFalse(self.service.dispatch(header, b"{}", secure_channel=secure)["ok"])
        self.assertEqual(self.calls, before)

    def test_admitted_request_can_finish_but_revocation_blocks_new_requests(self):
        entered, release = threading.Event(), threading.Event()
        results = {}
        original = self.service._preflight
        def blocked():
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test deadline")
            return original()
        with patch.object(self.service, "_preflight", side_effect=blocked):
            worker = threading.Thread(target=lambda: results.update(self.call()))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                self.snapshot = ()
                self.assertEqual(self.call()["error"], "authentication_failed")
            finally:
                release.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(results["ok"])

    def test_static_credentials_remain_supported_and_unambiguous(self):
        self.service = self.make((credential(OLD),), provider=False)
        self.assertTrue(self.call()["ok"])
        with self.assertRaises(core.InstallerError):
            self.make((credential(OLD),))
        with self.assertRaises(core.InstallerError):
            self.make((), provider=False)

    def test_empty_provider_allowed_at_startup_and_invalid_provider_rejected(self):
        self.snapshot = ()
        self.service = self.make()
        self.assertEqual(self.call()["error"], "authentication_failed")
        self.snapshot = []
        with self.assertRaisesRegex(core.InstallerError, "credentials_unavailable"):
            self.make()


if __name__ == "__main__":
    unittest.main()
