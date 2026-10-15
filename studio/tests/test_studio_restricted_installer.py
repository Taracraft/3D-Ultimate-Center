"""Installer boundary acceptance with synthetic archives, no network or engines."""
from dataclasses import asdict, replace
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Slicer-Server"))
import engine_catalog as catalog
import package_activation as activation
import restricted_installer as installer
import package_staging as staging

TOKEN = "s" * 64
OTHER_TOKEN = "t" * 64


def fixtures():
    archives = {}
    releases = []
    for engine, entry in catalog.ENTRYPOINTS.items():
        profile = {"bambu_studio": "resources/profiles/base.json",
                   "prusaslicer": "resources/base.ini",
                   "curaengine": "resources/definitions/base.def.json"}[engine]
        files = [(entry, b"synthetic engine", "engine", True),
                 ("licenses/NOTICE", b"synthetic only", "license", False),
                 ("resources/data.bin", b"data", "resources", False),
                 (profile, b"{}", "profiles", False)]
        if engine == "prusaslicer":
            files.append(("lib/OCCTWrapper.so", b"synthetic module", "runtime", False))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for path, data, _, _ in files:
                z.writestr(path, data)
        data = buf.getvalue()
        ident = engine + "_test"
        archives[ident] = data
        specs = [{"path": path, "sha256": hashlib.sha256(b).hexdigest(),
                  "size_bytes": len(b), "role": role, "executable": executable}
                 for path, b, role, executable in files]
        releases.append({"engine": engine, "version": "1.0.0", "system": "linux",
                         "architecture": "amd64", "artifacts": [{
                             "id": ident, "component_version": "1.0.0",
                             "url": "https://deb.debian.org/debian/pool/synthetic.zip",
                             "sha256": hashlib.sha256(data).hexdigest(),
                             "size_bytes": len(data), "format": "zip",
                             "license": "synthetic-test",
                             "source_url": catalog.UPSTREAMS[engine] + "tree/" + "b" * 40,
                             "source_revision": "b" * 40, "files": specs}]})
    return json.dumps({"schema": 1, "releases": releases, "pending": []}).encode(), archives


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.control = self.base / "control"
        self.control.mkdir(mode=0o700)
        self.parent = self.base / "volume"
        self.parent.mkdir(mode=0o700)
        self.policy = installer.HostPolicy("linux", "amd64", "managed_docker",
                                           True, True, self.parent / "engines", self.control)
        self.data, self.archives = fixtures()
        self.stops = 0
        self.credentials = [
            installer.Credential("homeassistant", hashlib.sha256(TOKEN.encode()).digest(),
                                 installer.SCOPES),
            installer.Credential("observer", hashlib.sha256(OTHER_TOKEN.encode()).digest(),
                                 frozenset(("inspect",))),
        ]
        self.service = self.make()
        self.seq = 0
        self.downloads = []
        def download(artifact, path, guard):
            guard.check()
            self.downloads.append(artifact.id)
            path.write_bytes(self.archives[artifact.id])
        self.addCleanup(patch.stopall)
        patch.object(staging, "_download", side_effect=download).start()
        patch.object(activation, "SPACE_MARGIN", 4096).start()
        patch.object(installer, "MARGIN", 4096).start()

    def stop(self):
        self.stops += 1
        return True

    def make(self, **kwargs):
        return installer.Installer(kwargs.pop("policy", self.policy), self.credentials,
                                   kwargs.pop("catalog_bytes", self.data),
                                   verify_volume=kwargs.pop("verify_volume", lambda: True),
                                   workers_stopped=kwargs.pop("workers_stopped", self.stop))

    def call(self, operation, *, token=TOKEN, secure=True, ident=None, **kwargs):
        request = {"protocol": 1, "operation": operation, **kwargs}
        if operation in installer.WRITE_FIELDS:
            self.seq += 1
            request["request_id"] = ident or f"{self.seq:032x}"
        return self.service.dispatch("Bearer " + token, json.dumps(request).encode(),
                                     secure_channel=secure)

    def ready(self):
        result = self.call("initialize")
        self.assertTrue(result["ok"], result)
        result = self.call("stage")
        self.assertEqual(result["state"], "prepared", result)
        return result["request_id"]

    def test_authentication_and_secure_channel_precede_parsing(self):
        for header, secure, expected in [
            ("", True, "authentication_failed"),
            ("Bearer " + "x" * 64, True, "authentication_failed"),
            ("Bearer " + TOKEN, False, "secure_transport_required"),
            ("Bearer " + TOKEN, 1, "secure_transport_required"),
        ]:
            result = self.service.dispatch(header, b"not JSON", secure_channel=secure)
            self.assertEqual(result, {"ok": False, "error": expected})
        self.assertFalse(self.policy.store.exists())
        self.assertNotIn(TOKEN, repr(self.credentials))

    def test_scopes_and_principal_isolation(self):
        self.assertTrue(self.call("preflight", token=OTHER_TOKEN)["ok"])
        self.assertEqual(self.call("initialize", token=OTHER_TOKEN)["error"], "forbidden")
        result = self.call("initialize")
        self.assertEqual(self.call("status", token=OTHER_TOKEN,
                                   target=result["request_id"])["error"], "forbidden")

    def test_duplicate_keys_protocol_bool_and_unknown_fields_rejected(self):
        for payload in [
            b'{"protocol":1,"operation":"preflight","operation":"stage"}',
            b'{"protocol":true,"operation":"preflight"}',
            b'{"protocol":1,"operation":"preflight","url":"https://evil.invalid"}',
            b'{"protocol":1,"operation":"preflight","secure_channel":true}',
            b'[]', b'{"protocol":1,"operation":"shell"}',
        ]:
            result = self.service.dispatch("Bearer " + TOKEN, payload, secure_channel=True)
            self.assertFalse(result["ok"])
        self.assertEqual(self.service.dispatch("Bearer " + TOKEN, b" " * 8193,
                                              secure_channel=True)["error"], "request_too_large")

    def test_requests_cannot_supply_paths_urls_commands_or_worker_ack(self):
        for field, value in [("path", "/etc"), ("url", "https://evil.invalid"),
                             ("command", ["docker", "run"]), ("workers_stopped", True),
                             ("catalog", {})]:
            result = self.call("initialize", **{field: value})
            self.assertEqual(result["error"], "invalid_request")
        self.assertFalse(self.policy.store.exists())

    def test_prerequisite_failures_have_actionable_codes(self):
        for policy, expected in [
            (replace(self.policy, system="windows"), "unsupported_platform"),
            (replace(self.policy, architecture="arm64"), "unsupported_platform"),
            (replace(self.policy, mode="ha_container"), "unsupported_host"),
            (replace(self.policy, installer_available=False), "installer_pairing_required"),
            (replace(self.policy, runtime_available=False), "runtime_adapter_required"),
        ]:
            self.service = self.make(policy=policy)
            self.assertIn(expected, self.call("preflight")["reasons"])
            self.assertEqual(self.call("initialize")["error"], expected)
        self.assertFalse(self.policy.store.exists())

    def test_unverified_volume_is_rejected_before_creation(self):
        self.service = self.make(verify_volume=lambda: False)
        self.assertEqual(self.call("initialize")["error"], "persistent_volume_unverified")
        self.assertFalse(self.policy.store.exists())

    def test_shipped_pending_catalog_never_downloads_or_activates(self):
        pending = (Path(__file__).resolve().parents[1] /
                   "Slicer-Server/engine_catalog.json").read_bytes()
        self.service = self.make(catalog_bytes=pending)
        self.assertIn("engine_releases_pending", self.call("preflight")["reasons"])
        self.assertEqual(self.call("stage")["error"], "engine_releases_pending")
        self.assertEqual(self.call("activate", target="1" * 32)["error"], "engine_releases_pending")
        self.assertEqual(self.downloads, [])

    def test_initialize_is_idempotent_and_binding_is_outside_store(self):
        ident = "a" * 32
        first = self.call("initialize", ident=ident)
        self.assertEqual(first, self.call("initialize", ident=ident))
        binding = json.loads((self.control / "BINDING.json").read_bytes())
        self.assertEqual(binding["store_path"], str(self.policy.store))
        self.assertTrue((self.policy.store / "STORE.json").exists())
        self.assertNotIn("store_path", json.dumps(first))
        self.assertEqual(self.call("stage", ident=ident)["error"], "request_id_conflict")

    def test_complete_synthetic_pipeline_and_restart_status(self):
        target = self.ready()
        result = self.call("activate", target=target, ident="a" * 32)
        self.assertEqual(result["state"], "activated", result)
        self.assertEqual(self.stops, 1)
        self.service = self.make()
        self.assertEqual(result, self.call("activate", target=target, ident="a" * 32))
        self.assertEqual(self.stops, 1)
        status = self.call("status", target="a" * 32)
        self.assertEqual(status["generation_id"], result["generation_id"])
        self.assertNotIn(str(self.base), json.dumps(status))
        self.assertEqual(set(self.downloads), set(self.archives))

    def test_stage_replay_does_not_repeat_downloads(self):
        self.call("initialize")
        first = self.call("stage", ident="b" * 32)
        self.service = self.make()
        self.assertEqual(first, self.call("stage", ident="b" * 32))
        self.assertEqual(len(self.downloads), 3)

    def test_wrong_store_identity_fails_after_restart(self):
        self.call("initialize")
        marker = self.policy.store / "STORE.json"
        value = json.loads(marker.read_bytes())
        value["store_id"] = "f" * 32
        marker.write_text(json.dumps(value))
        self.service = self.make()
        self.assertFalse(self.call("stage")["ok"])
        self.assertEqual(self.downloads, [])

    def test_worker_ack_is_not_inferred_from_catalog_or_payload(self):
        target = self.ready()
        self.service = self.make(workers_stopped=lambda: False)
        result = self.call("activate", target=target)
        self.assertFalse(result["ok"])
        self.assertFalse((self.policy.store / "ACTIVE.json").exists())

    def test_post_stage_tampering_is_rejected(self):
        target = self.ready()
        state = json.loads((self.control / "records" / (target + ".json")).read_bytes())
        candidate = Path(state["candidates"]["curaengine"])
        (candidate / "payload/curaengine/bin/CuraEngine").write_bytes(b"tampered")
        self.assertFalse(self.call("activate", target=target)["ok"])
        self.assertEqual(self.stops, 0)
        self.assertFalse((self.policy.store / "ACTIVE.json").exists())

    def test_catalog_change_invalidates_old_preparation(self):
        target = self.ready()
        self.service = self.make(catalog_bytes=self.data + b" ")
        self.assertEqual(self.call("activate", target=target)["error"], "candidate_not_current")
        self.assertEqual(self.stops, 0)

    def test_candidate_receipt_cannot_grant_new_release_authority(self):
        target = self.ready()
        state = json.loads((self.control / "records" / (target + ".json")).read_bytes())
        receipt = Path(state["candidates"]["curaengine"]) / "READY.json"
        value = json.loads(receipt.read_bytes())
        value["release"]["version"] = "9.9.9"
        receipt.write_text(json.dumps(value))
        self.assertEqual(self.call("activate", target=target)["error"], "candidate_not_current")
        self.assertEqual(self.stops, 0)

    def test_parallel_writer_is_rejected(self):
        with activation._store_lock(self.control):
            result = self.call("initialize")
        self.assertFalse(result["ok"])
        self.assertFalse(self.policy.store.exists())

    def test_cancel_active_stage_then_explicit_retry(self):
        self.call("initialize")
        entered = threading.Event()
        release = threading.Event()
        def blocked(artifact, path, guard):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            guard.check()
            path.write_bytes(self.archives[artifact.id])
        result = {}
        with patch.object(staging, "_download", side_effect=blocked):
            t = threading.Thread(target=lambda: result.update(
                self.call("stage", ident="c" * 32)))
            t.start()
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.call("status", target="c" * 32)["state"], "running")
                self.assertEqual(self.call("cancel", target="c" * 32)["state"], "cancel_requested")
            finally:
                release.set()
                t.join(5)
        self.assertFalse(t.is_alive())
        self.assertFalse(result["ok"])
        self.assertEqual(self.call("status", target="c" * 32)["state"], "cancelled")
        self.assertEqual(self.call("retry", target="c" * 32)["state"], "prepared")
        self.assertEqual(self.stops, 0)

    def test_failed_download_is_sanitized_and_retryable(self):
        self.call("initialize")
        with patch.object(staging, "_download", side_effect=OSError("/private/secret")):
            result = self.call("stage", ident="d" * 32)
        self.assertFalse(result["ok"])
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(self.call("status", target="d" * 32)["state"], "failed")
        self.assertEqual(self.call("retry", target="d" * 32)["state"], "prepared")

    def test_insufficient_space_prevents_download(self):
        self.call("initialize")
        usage = installer.shutil.disk_usage(self.policy.store)
        with patch.object(installer.shutil, "disk_usage",
                          return_value=type(usage)(usage.total, usage.used, 1)):
            self.assertEqual(self.call("stage")["error"], "insufficient_space")
        self.assertEqual(self.downloads, [])

    def test_orphan_stage_requires_explicit_abort(self):
        self.call("initialize")
        with patch.object(staging, "prepare_release", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.call("stage", ident="e" * 32)
        self.service = self.make()
        self.assertEqual(self.call("stage")["error"], "recovery_required")
        self.assertEqual(self.call("recover", target="e" * 32, action="abort")["state"], "recovered")
        self.assertEqual(self.call("retry", target="e" * 32)["state"], "prepared")

    def test_recovery_failure_must_not_create_second_orphan(self):
        self.call("initialize")
        with patch.object(staging, "prepare_release", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.call("stage", ident="e" * 32)
        self.assertFalse(self.call("recover", target="e" * 32, action="adopt")["ok"])
        result = self.call("recover", target="e" * 32, action="abort")
        self.assertEqual(result["state"], "recovered", result)

    def test_declined_candidate_must_not_block_valid_future_work(self):
        target = self.ready()
        self.assertFalse(self.call("activate", target="0" * 32)["ok"])
        result = self.call("activate", target=target)
        self.assertEqual(result["state"], "activated", result)

    def test_control_store_overlap_rejected(self):
        with self.assertRaisesRegex(installer.InstallerError, "control_store_overlap"):
            self.make(policy=replace(self.policy, store=self.control / "store"))

    def test_private_control_permissions(self):
        if os.name == "nt":
            self.skipTest("POSIX control directory permissions")
        self.control.chmod(0o777)
        with self.assertRaises(activation.ActivationError):
            self.make()
        self.control.chmod(0o700)

    def test_crash_after_activation_switch_can_be_adopted(self):
        target = self.ready()
        save = self.service._save
        def crash(row):
            if row.get("state") == "activated":
                raise KeyboardInterrupt()
            save(row)
        with patch.object(self.service, "_save", side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):
                self.call("activate", target=target, ident="f" * 32)
        self.service = self.make()
        result = self.call("recover", target="f" * 32, action="adopt")
        self.assertEqual(result["state"], "recovered", result)
        self.assertEqual(self.call("status", target="f" * 32)["state"], "adopted")
        self.assertTrue((self.policy.store / "ACTIVE.json").exists())

    def test_inner_activation_orphan_is_resolved_by_same_generation(self):
        target = self.ready()
        original = activation._atomic_json
        def crash(path, value):
            if path.parent == self.policy.store / "transactions" and value.get("state") == "activated":
                raise OSError("synthetic crash")
            original(path, value)
        with patch.object(activation, "_atomic_json", side_effect=crash):
            self.assertFalse(self.call("activate", target=target, ident="f" * 32)["ok"])
        result = self.call("recover", target="f" * 32, action="adopt")
        self.assertEqual(result["state"], "recovered", result)
        self.assertEqual(self.call("status", target="f" * 32)["state"], "adopted")

    def test_lost_volume_after_worker_stop_prevents_pointer_switch(self):
        target = self.ready()
        mounted = {"value": True}
        def stop():
            mounted["value"] = False
            return True
        self.service = self.make(verify_volume=lambda: mounted["value"], workers_stopped=stop)
        self.assertFalse(self.call("activate", target=target)["ok"])
        self.assertFalse((self.policy.store / "ACTIVE.json").exists())

    def test_pending_catalog_does_not_prevent_recovery(self):
        self.call("initialize")
        with patch.object(staging, "prepare_release", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.call("stage", ident="e" * 32)
        pending = (Path(__file__).resolve().parents[1] /
                   "Slicer-Server/engine_catalog.json").read_bytes()
        self.service = self.make(catalog_bytes=pending)
        self.assertEqual(self.call("recover", target="e" * 32, action="abort")["state"], "recovered")

    def test_symlink_control_is_rejected(self):
        alias = self.base / "alias"
        try:
            alias.symlink_to(self.control, target_is_directory=True)
        except OSError:
            self.skipTest("symlink unavailable")
        with self.assertRaises(activation.ActivationError):
            self.make(policy=replace(self.policy, control=alias))

    def test_receipt_capacity_is_bounded_without_deleting_history(self):
        first = self.call("initialize")
        with patch.object(installer, "MAX_RECORDS", 1):
            self.assertEqual(self.call("stage")["error"], "history_capacity")
        self.assertEqual(self.call("status", target=first["request_id"])["state"], "initialized")

    def test_install_before_initialize_returns_explicit_state(self):
        self.assertEqual(self.call("stage")["error"], "storage_not_initialized")


if __name__ == "__main__":
    unittest.main()
