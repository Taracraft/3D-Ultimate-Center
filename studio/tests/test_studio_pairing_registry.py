"""Synthetic pairing registry acceptance. No listener or real host provisioning."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Slicer-Server"))
import pairing_registry as pairing
import restricted_installer as core


class PairingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "pairing"
        self.root.mkdir(mode=0o700)
        self.host_id = pairing.initialize(self.root)
        self.registry = pairing.Registry(self.root, self.host_id)

    def issue(self, name="homeassistant"):
        return self.registry.issue(name, core.SCOPES)

    def state(self):
        return json.loads((self.root / "REGISTRY.json").read_bytes())

    def replace_state(self, state):
        (self.root / "REGISTRY.json").write_text(json.dumps(state), encoding="ascii")

    def test_issue_stores_only_digest_and_restart_preserves_identity(self):
        token = self.issue()
        self.assertEqual(len(token), 64)
        data = (self.root / "REGISTRY.json").read_text()
        self.assertNotIn(token, data)
        restarted = pairing.Registry(self.root, self.host_id)
        self.assertEqual(restarted.snapshot()[0].token_sha256,
                         hashlib.sha256(token.encode()).digest())
        self.assertEqual(self.state()["revision"], 1)

    def test_rotate_keeps_principal_and_changes_digest_and_scopes(self):
        old = self.issue()
        new = self.registry.rotate("homeassistant", scopes=frozenset(("inspect",)))
        self.assertNotEqual(old, new)
        entry = self.registry.snapshot()[0]
        self.assertEqual(entry.principal, "homeassistant")
        self.assertEqual(entry.scopes, frozenset(("inspect",)))
        self.assertEqual(entry.token_sha256, hashlib.sha256(new.encode()).digest())
        self.assertEqual(self.state()["revision"], 2)

    def test_revocation_is_durable_idempotent_and_reserves_principal(self):
        self.issue()
        self.registry.revoke("homeassistant")
        before = (self.root / "REGISTRY.json").read_bytes()
        self.registry.revoke("homeassistant")
        self.assertEqual(before, (self.root / "REGISTRY.json").read_bytes())
        self.assertEqual(pairing.Registry(self.root, self.host_id).snapshot(), ())
        for fn in [lambda: self.issue(), lambda: self.registry.rotate("homeassistant")]:
            with self.assertRaises(pairing.RegistryError):
                fn()

    def test_pinned_installation_identity_rejects_other_registry(self):
        with self.assertRaises(pairing.RegistryError):
            pairing.Registry(self.root, "f" * 32)
        state = self.state()
        state["host_id"] = "e" * 32
        self.replace_state(state)
        with self.assertRaises(pairing.RegistryError):
            self.registry.snapshot()

    def test_reinitialization_and_foreign_directory_rejected(self):
        with self.assertRaises(pairing.RegistryError):
            pairing.initialize(self.root)
        other = self.root.parent / "foreign"
        other.mkdir(mode=0o700)
        (other / "userdata").write_text("keep")
        with self.assertRaises(pairing.RegistryError):
            pairing.initialize(other)
        self.assertEqual((other / "userdata").read_text(), "keep")

    def test_invalid_admin_input_leaves_state_unchanged(self):
        before = (self.root / "REGISTRY.json").read_bytes()
        for name, scopes in [("UPPER", core.SCOPES), ("x", frozenset()),
                             ("x", {"inspect"}), ("x", frozenset(("shell",)))]:
            with self.assertRaises(pairing.RegistryError):
                self.registry.issue(name, scopes)
        with self.assertRaises(pairing.RegistryError):
            self.registry.revoke("missing")
        self.assertEqual((self.root / "REGISTRY.json").read_bytes(), before)

    def test_capacity_includes_tombstones(self):
        self.issue()
        self.registry.revoke("homeassistant")
        with patch.object(pairing, "MAX_PRINCIPALS", 1):
            with self.assertRaisesRegex(pairing.RegistryError, "registry_capacity"):
                self.issue("another")

    def test_duplicate_principals_digests_and_scopes_rejected(self):
        self.issue()
        base = self.state()
        for kind in ("principal", "digest", "scopes"):
            state = json.loads(json.dumps(base))
            second = dict(state["entries"][0])
            if kind == "principal":
                second["token_sha256"] = "f" * 64
                state["entries"].append(second)
            elif kind == "digest":
                second["principal"] = "another"
                state["entries"].append(second)
            else:
                state["entries"][0]["scopes"] = ["inspect", "inspect"]
            self.replace_state(state)
            with self.assertRaises(ValueError):
                self.registry.snapshot()

    def test_duplicate_json_and_oversize_rejected(self):
        path = self.root / "REGISTRY.json"
        for data in [b'{"schema":1,"schema":1}', b" " * (pairing.MAX_BYTES + 1)]:
            path.write_bytes(data)
            with self.assertRaises(pairing.RegistryError):
                self.registry.snapshot()

    def test_missing_and_corrupt_storage_fail_closed_in_installer(self):
        token = self.issue()
        control = self.root.parent / "control"
        control.mkdir(mode=0o700)
        policy = core.HostPolicy("linux", "amd64", "managed_docker", True, True,
                                 self.root.parent / "engines", control)
        catalog = json.dumps({"schema":1,"releases":[],
                              "pending":sorted(core.catalog.ENTRYPOINTS)}).encode()
        service = core.Installer(policy, (), catalog, verify_volume=lambda: True,
                                 workers_stopped=lambda: True,
                                 credential_provider=self.registry.snapshot)
        body = b'{"protocol":1,"operation":"preflight"}'
        def call(secret):
            return service.dispatch("Bearer " + secret, body, secure_channel=True)
        self.assertTrue(call(token)["ok"])
        new = self.registry.rotate("homeassistant")
        self.assertEqual(call(token)["error"], "authentication_failed")
        self.assertTrue(call(new)["ok"])
        self.registry.revoke("homeassistant")
        self.assertEqual(call(new)["error"], "authentication_failed")
        (self.root / "REGISTRY.json").write_text("broken")
        self.assertEqual(call(new)["error"], "credentials_unavailable")
        (self.root / "REGISTRY.json").unlink()
        self.assertEqual(call(new)["error"], "credentials_unavailable")

    def test_failed_replace_retains_previous_credentials_and_cleans_temporary(self):
        old = self.issue()
        before = (self.root / "REGISTRY.json").read_bytes()
        with patch.object(pairing.activation.os, "replace", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                self.registry.rotate("homeassistant")
        self.assertEqual((self.root / "REGISTRY.json").read_bytes(), before)
        self.assertEqual(set(p.name for p in self.root.iterdir()),
                         {".registry.lock", "REGISTRY.json"})
        self.assertEqual(self.registry.snapshot()[0].token_sha256,
                         hashlib.sha256(old.encode()).digest())

    def test_post_replace_sync_failure_is_uncertain_not_reported_success(self):
        self.issue()
        before = self.state()["revision"]
        with patch.object(pairing.activation, "_fsync_directory", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                self.registry.rotate("homeassistant")
        self.assertEqual(self.state()["revision"], before + 1)
        # Caller did not receive a token. Explicit subsequent rotation is safe.
        new = self.registry.rotate("homeassistant")
        self.assertEqual(self.registry.snapshot()[0].token_sha256,
                         hashlib.sha256(new.encode()).digest())

    def test_second_writer_rejected_while_snapshots_remain_readable(self):
        with pairing._locked(self.root):
            self.assertEqual(self.registry.snapshot(), ())
            with self.assertRaisesRegex(pairing.RegistryError, "registry_busy"):
                self.issue()

    def test_secret_collision_rejected_without_overwriting(self):
        token = self.issue()
        before = (self.root / "REGISTRY.json").read_bytes()
        with patch.object(pairing.secrets, "token_urlsafe", return_value=token):
            with self.assertRaises(ValueError):
                self.issue("another")
        self.assertEqual((self.root / "REGISTRY.json").read_bytes(), before)

    def test_hardlinked_registry_rejected(self):
        path = self.root / "REGISTRY.json"
        alias = self.root.parent / "alias"
        try:
            os.link(path, alias)
        except OSError:
            self.skipTest("hardlink unavailable")
        with self.assertRaises(pairing.RegistryError):
            self.registry.snapshot()

    def test_symlink_registry_and_lock_rejected(self):
        for name in ("REGISTRY.json", ".registry.lock"):
            path = self.root / name
            saved = path.read_bytes()
            target = self.root.parent / ("target-" + name)
            target.write_bytes(saved)
            path.unlink()
            try:
                path.symlink_to(target)
            except OSError:
                path.write_bytes(saved)
                self.skipTest("symlink unavailable")
            try:
                with self.assertRaises(ValueError):
                    self.registry.snapshot() if name == "REGISTRY.json" else self.issue()
            finally:
                path.unlink()
                path.write_bytes(saved)
                path.chmod(0o600)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX special file")
    def test_fifo_rejected_before_open_without_blocking(self):
        path = self.root / "REGISTRY.json"
        path.unlink()
        os.mkfifo(path, 0o600)
        with patch.object(pairing.os, "open", side_effect=AssertionError("must not open FIFO")):
            with self.assertRaises(pairing.RegistryError):
                self.registry.snapshot()

    @unittest.skipIf(os.name == "nt", "POSIX ownership and modes")
    def test_private_modes_required_for_directory_registry_and_lock(self):
        for path, mode in [(self.root, 0o755), (self.root/"REGISTRY.json", 0o644),
                           (self.root/".registry.lock", 0o644)]:
            original = path.stat().st_mode & 0o777
            path.chmod(mode)
            try:
                with self.assertRaises(pairing.RegistryError):
                    self.issue()
            finally:
                path.chmod(original)

    @unittest.skipIf(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                         "requires isolated root fixture")
    def test_foreign_owner_rejected(self):
        path = self.root / "REGISTRY.json"
        os.chown(path, 65532, 65532)
        try:
            with self.assertRaises(pairing.RegistryError):
                self.registry.snapshot()
        finally:
            os.chown(path, 0, 0)


if __name__ == "__main__":
    unittest.main()
