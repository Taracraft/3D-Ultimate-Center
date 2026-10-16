"""Synthetic protected connection transfer; no real server, credential, or HA install."""
from __future__ import annotations
import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio"
PKG = "studio_connection_handoff_test"
package = sys.modules.setdefault(PKG, type(sys)(PKG))
package.__path__ = [str(COMP)]
const = type(sys)(PKG + ".const")
const.DOMAIN = "ultimate_3d_studio"
sys.modules[PKG + ".const"] = const


def load(name):
    full = PKG + "." + name
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, COMP / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


handoff = load("slicer_connection_handoff")
runtime = load("slicer_installer_runtime")
HOST = "a" * 32
TRANSFER = "b" * 32
KEY = "X" * 64
URL = "https://slicer.invalid:8443"


def record(**changes):
    value = {"schema": 1, "host_id": HOST, "principal": "ha", "transfer_id": TRANSFER,
             "base_url": URL, "api_secret": KEY}
    value.update(changes)
    return value


def wire(**changes):
    return json.dumps(record(**changes), sort_keys=True, separators=(",", ":")).encode("ascii")


def decode(raw):
    return handoff.decode_connection_offer(raw, expected_host_id=HOST, expected_principal="ha")


def put(root, raw=None):
    path = root / handoff.CONNECTION_FILE
    if path.exists():
        path.chmod(0o600)
    path.write_bytes(wire() if raw is None else raw)
    path.chmod(0o400)
    return path


class DecoderTests(unittest.TestCase):
    def test_roundtrip_and_repr_do_not_expose_secret(self):
        value = decode(wire())
        self.assertEqual(value.base_url, URL)
        self.assertEqual(value.api_secret, KEY)
        self.assertNotIn(KEY, repr(value))
        self.assertNotIn(URL, repr(value))
        self.assertEqual(value.raw_sha256, hashlib.sha256(wire()).hexdigest())

    def test_encoder_uses_same_strict_schema(self):
        actual = handoff.encode_connection_offer(host_id=HOST, principal="ha", transfer_id=TRANSFER,
                                                base_url=URL, api_secret=KEY)
        self.assertEqual(actual, wire())

    def test_schema_rejects_boolean_and_wrong_types(self):
        for value in (True, False, "1", 1.0, None, 2, [], {}):
            with self.subTest(value=value), self.assertRaises(handoff.ConnectionHandoffError):
                decode(wire(schema=value))

    def test_duplicate_and_nonfinite_json_are_rejected(self):
        for raw in (wire()[:-1] + b',"schema":1}', wire().replace(b'"schema":1', b'"schema":NaN'),
                    wire().replace(b'"schema":1', b'"schema":Infinity')):
            with self.subTest(raw=raw[:20]), self.assertRaises(handoff.ConnectionHandoffError):
                decode(raw)

    def test_missing_or_unknown_fields_are_rejected(self):
        for field in record():
            value = record()
            value.pop(field)
            with self.subTest(field=field), self.assertRaises(handoff.ConnectionHandoffError):
                decode(json.dumps(value).encode())
        with self.assertRaises(handoff.ConnectionHandoffError):
            decode(wire(extra="not allowed"))

    def test_host_and_principal_must_match_separate_pins(self):
        for value in (record(host_id="c" * 32), record(principal="other")):
            with self.subTest(value=value["principal"]), self.assertRaises(handoff.ConnectionHandoffError):
                decode(json.dumps(value).encode())

    def test_transfer_identity_must_be_exact(self):
        for value in ("", "C" * 32, "a" * 31, True, "../other", None):
            with self.subTest(value=value), self.assertRaises(handoff.ConnectionHandoffError):
                decode(wire(transfer_id=value))

    def test_automatic_connection_requires_canonical_https(self):
        for value in ("http://localhost:8000", "http://127.0.0.1", "http://slicer.invalid", URL + "/",
                      "https://user:pass@slicer.invalid", URL + "?token=other", URL + "#fragment",
                      "https://slicer.invalid/path", "https://0.0.0.0", "https://169.254.1.1"):
            with self.subTest(value=value), self.assertRaises(handoff.ConnectionHandoffError):
                decode(wire(base_url=value))

    def test_secret_header_injection_and_invalid_lengths_are_rejected(self):
        for value in ("x" * 31, "x" * 257, "x" * 32 + "\r\nNext: header", "x" * 32 + " ", None, 42):
            with self.subTest(type=type(value).__name__), self.assertRaises(handoff.ConnectionHandoffError) as caught:
                decode(wire(api_secret=value))
            self.assertEqual(str(caught.exception), "invalid_connection_handoff")

    def test_payload_is_bounded_ascii_bytes(self):
        for value in (b"", b"x" * 8193, b"\xef\xbb\xbf" + wire(), "not bytes", bytearray(wire())):
            with self.subTest(type=type(value).__name__), self.assertRaises(handoff.ConnectionHandoffError):
                decode(value)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "handoff"
        self.root.mkdir(mode=0o700)
        self.owner = os.geteuid() if hasattr(os, "geteuid") else 0
        self.path = put(self.root)

    def read(self):
        return handoff.read_connection_offer(self.root, server_uid=self.owner,
                                             expected_host_id=HOST, expected_principal="ha")

    def test_reader_retains_protected_original(self):
        before = self.path.read_bytes()
        offer = self.read()
        self.assertEqual(offer.api_secret, KEY)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(offer.same_file(self.read()))

    def test_missing_file_is_not_recreated(self):
        self.path.chmod(0o600)
        self.path.unlink()
        with self.assertRaisesRegex(handoff.ConnectionHandoffError, "connection_handoff_missing"):
            self.read()
        self.assertFalse(self.path.exists())

    def test_oversized_file_is_rejected_before_parse(self):
        put(self.root, b"x" * 8193)
        with self.assertRaisesRegex(handoff.ConnectionHandoffError, "unsafe_connection_handoff"):
            self.read()

    def test_hardlinks_are_rejected(self):
        alias = self.root / "alias.json"
        os.link(self.path, alias)
        def cleanup_alias():
            if alias.exists():
                alias.chmod(0o600)
                alias.unlink()
        self.addCleanup(cleanup_alias)
        with self.assertRaisesRegex(handoff.ConnectionHandoffError, "unsafe_connection_handoff"):
            self.read()

    def test_non_regular_file_is_rejected(self):
        self.path.chmod(0o600)
        self.path.unlink()
        self.path.mkdir()
        with self.assertRaisesRegex(handoff.ConnectionHandoffError, "unsafe_connection_handoff"):
            self.read()

    def test_symbolic_link_is_rejected(self):
        alias = self.root / "original.json"
        self.path.chmod(0o600)
        self.path.rename(alias)
        try:
            self.path.symlink_to(alias)
        except OSError:
            self.skipTest("symbolic link privilege unavailable")
        with self.assertRaisesRegex(handoff.ConnectionHandoffError, "unsafe_connection_handoff"):
            self.read()

    def test_changed_content_invalidates_witness(self):
        before = self.read()
        put(self.root, wire(transfer_id="c" * 32))
        self.assertFalse(before.same_file(self.read()))

    def test_equal_replacement_bytes_still_change_file_identity(self):
        before = self.read()
        temp = self.root / "replacement.json"
        temp.write_bytes(wire())
        temp.chmod(0o400)
        self.path.chmod(0o600)
        os.replace(temp, self.path)
        self.assertFalse(before.same_file(self.read()))

    def test_descriptor_stat_change_is_detected(self):
        actual = os.fstat
        calls = []
        def changed(fd):
            value = actual(fd)
            calls.append(fd)
            if len(calls) == 2:
                fields = {k: getattr(value, k) for k in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")}
                fields["st_size"] += 1
                return SimpleNamespace(**fields)
            return value
        with patch.object(handoff.os, "fstat", side_effect=changed):
            with self.assertRaisesRegex(handoff.ConnectionHandoffError, "connection_handoff_changed"):
                self.read()

    def test_descriptor_change_time_change_during_read_is_rejected(self):
        actual = os.fstat
        calls = []
        def changed(fd):
            value = actual(fd)
            calls.append(fd)
            if len(calls) == 2:
                fields = {k: getattr(value, k) for k in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")}
                fields["st_ctime_ns"] += 100
                return SimpleNamespace(**fields)
            return value
        with patch.object(handoff.os, "fstat", side_effect=changed):
            with self.assertRaisesRegex(handoff.ConnectionHandoffError, "connection_handoff_changed"):
                self.read()

    @unittest.skipIf(os.name == "nt", "POSIX ownership and permissions")
    def test_wrong_file_mode_is_rejected(self):
        self.path.chmod(0o600)
        with self.assertRaisesRegex(handoff.ConnectionHandoffError, "unsafe_connection_handoff"):
            self.read()

    @unittest.skipIf(os.name == "nt", "POSIX ownership and permissions")
    def test_writable_shared_directory_is_rejected(self):
        self.root.chmod(0o770)
        with self.assertRaisesRegex(handoff.ConnectionHandoffError, "unsafe_connection_handoff"):
            self.read()

    @unittest.skipIf(os.name == "nt", "POSIX ownership and permissions")
    def test_unexpected_directory_owner_is_rejected(self):
        with self.assertRaisesRegex(handoff.ConnectionHandoffError, "unsafe_connection_handoff"):
            handoff.read_connection_offer(self.root, server_uid=self.owner + 1,
                                          expected_host_id=HOST, expected_principal="ha")

    def test_production_publisher_refuses_non_linux_context(self):
        with patch.object(handoff.sys, "platform", "win32"):
            with self.assertRaisesRegex(handoff.ConnectionHandoffError, "connection_publisher_unavailable"):
                handoff.publish_connection_offer(self.root, host_id=HOST, principal="ha", transfer_id=TRANSFER,
                    base_url=URL, api_secret=KEY, recipient_uid=0, recipient_gid=0)


class MetadataSemanticsTests(unittest.TestCase):
    def info(self, **changes):
        fields = {"st_dev": 1, "st_ino": 2, "st_mode": 0o100400, "st_uid": 0,
                  "st_gid": 0, "st_nlink": 1, "st_size": 20, "st_mtime_ns": 100,
                  "st_ctime_ns": 100}
        fields.update(changes)
        return SimpleNamespace(**fields)

    def test_windows_creation_and_change_times_are_not_compared_cross_api(self):
        with patch.object(handoff.os, "name", "nt"):
            self.assertTrue(handoff._same_open_file(self.info(), self.info(st_ctime_ns=200)))

    def test_posix_cross_api_change_time_remains_mandatory(self):
        with patch.object(handoff.os, "name", "posix"):
            self.assertFalse(handoff._same_open_file(self.info(), self.info(st_ctime_ns=200)))

    def test_cross_api_identity_mode_size_and_mtime_remain_mandatory(self):
        for field in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns"):
            with self.subTest(field=field), patch.object(handoff.os, "name", "nt"):
                value = getattr(self.info(), field)
                self.assertFalse(handoff._same_open_file(self.info(), self.info(**{field: value + 1})))

    def test_same_api_identity_always_keeps_change_time(self):
        self.assertNotEqual(handoff._stat_identity(self.info()), handoff._stat_identity(self.info(st_ctime_ns=200)))



class FakeHass:
    def __init__(self):
        self.data = {}
        self.threads = []
    def async_create_task(self, coro):
        return asyncio.create_task(coro)
    async def async_add_executor_job(self, function, *args):
        def call():
            self.threads.append(threading.get_ident())
            return function(*args)
        return await asyncio.to_thread(call)


class ConnectionAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "handoff"
        self.directory.mkdir(mode=0o700)
        self.path = put(self.directory)
        self.hass = FakeHass()
        self.entry = SimpleNamespace(entry_id="fixture-entry", data={"instance_name": "fixture"},
            options={"cloud_enabled": True, "printer_name": "fixture", "slicer_enabled": False,
                     "slicer_base_url": "https://previous.invalid", "slicer_api_secret": "O" * 64})
        self.before = copy.deepcopy(self.entry.options)
        self.credential = {"credential_stored": True, "host_id": HOST, "principal": "ha"}
        self.host_calls = []
        self.controller = SimpleNamespace(backend=SimpleNamespace(credential_status=lambda: dict(self.credential)))
        def run(action, **kwargs):
            self.host_calls.append(action)
            return {"ok": True, "state": "initialized" if action == "initialize" else "running"}
        self.controller.run = run
        self.endpoint = [SimpleNamespace(host_id=HOST, server_uid=os.geteuid() if hasattr(os, "geteuid") else 0,
                                        handoff_directory=str(self.directory), socket_directory=str(self.root / "sockets"))]
        self.probe_calls = []
        self.probe_error = None
        self.probe_mutation = None
        self.probe_started = asyncio.Event()
        self.probe_release = asyncio.Event()
        self.block_probe = False
        async def probe(hass, url, key):
            self.probe_calls.append((url, key))
            self.probe_started.set()
            if self.block_probe:
                await self.probe_release.wait()
            if self.probe_mutation:
                self.probe_mutation()
            if self.probe_error:
                raise ValueError(self.probe_error)
            return {"status": "ready", "api_protocol": 2, "server_version": "fixture"}
        self.session = runtime.InstallerSession(self.hass, self.root / "state", entry=self.entry,
            endpoint_loader=lambda: self.endpoint[0], controller_factory=lambda *_: self.controller,
            connection_probe=probe)

    async def asyncTearDown(self):
        self.probe_release.set()
        await self.session.async_close()
        if self.path.is_file():
            self.path.chmod(0o600)

    async def prepare(self):
        return await self.session.async_run("configure_connection")

    async def test_verified_connection_is_private_until_native_flow_completion(self):
        result = await self.prepare()
        self.assertEqual(result, {"ok": True, "state": "connection_verified"})
        self.assertEqual(self.entry.options, self.before)
        self.assertEqual(self.host_calls, [])
        self.assertEqual(self.probe_calls, [(URL, KEY)])
        for value in (result, self.session.snapshot()):
            self.assertNotIn(KEY, json.dumps(value))
            self.assertNotIn(URL, json.dumps(value))
        options = await self.session.async_connection_options(self.entry)
        self.assertEqual(options["slicer_api_secret"], KEY)
        self.assertEqual(options["slicer_base_url"], URL)
        self.assertIs(options["slicer_enabled"], True)
        self.assertTrue(options["cloud_enabled"])
        self.assertEqual(options["printer_name"], "fixture")
        self.assertEqual(self.path.read_bytes(), wire())
        self.assertIsNone(await self.session.async_connection_options(self.entry))

    async def test_disk_io_runs_outside_event_loop(self):
        await self.prepare()
        await self.session.async_connection_options(self.entry)
        self.assertTrue(self.hass.threads)
        self.assertNotIn(threading.get_ident(), self.hass.threads)

    async def test_certificate_failure_preserves_old_connection(self):
        self.probe_error = "slicer_certificate_error"
        result = await self.prepare()
        self.assertEqual(result["error"], "slicer_certificate_error")
        self.assertIsNone(await self.session.async_connection_options(self.entry))
        self.assertEqual(self.entry.options, self.before)
        self.assertEqual(self.path.read_bytes(), wire())

    async def test_authentication_failure_does_not_apply_secret(self):
        self.probe_error = "slicer_auth_required"
        result = await self.prepare()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "slicer_auth_required")
        self.assertEqual(self.entry.options, self.before)

    async def test_redirect_failure_does_not_apply_secret(self):
        self.probe_error = "slicer_redirect_refused"
        self.assertEqual((await self.prepare())["error"], "slicer_redirect_refused")
        self.assertIsNone(await self.session.async_connection_options(self.entry))

    async def test_missing_handoff_has_no_network_or_host_call(self):
        self.path.chmod(0o600)
        self.path.unlink()
        result = await self.prepare()
        self.assertEqual(result["error"], "connection_handoff_missing")
        self.assertEqual(self.probe_calls, [])
        self.assertEqual(self.host_calls, [])

    async def test_different_principal_has_no_network_call(self):
        put(self.directory, wire(principal="other"))
        self.assertEqual((await self.prepare())["error"], "invalid_connection_handoff")
        self.assertEqual(self.probe_calls, [])

    async def test_missing_pairing_cannot_read_offer(self):
        self.credential["credential_stored"] = False
        self.assertEqual((await self.prepare())["error"], "installer_pairing_required")
        self.assertEqual(self.probe_calls, [])

    async def test_change_during_probe_rejects_offer(self):
        self.probe_mutation = lambda: put(self.directory, wire(transfer_id="c" * 32))
        self.assertEqual((await self.prepare())["error"], "connection_handoff_changed")
        self.assertIsNone(await self.session.async_connection_options(self.entry))

    async def test_user_connection_change_during_probe_is_preserved(self):
        self.probe_mutation = lambda: self.entry.options.update(slicer_base_url="https://user-choice.invalid")
        self.assertEqual((await self.prepare())["error"], "connection_configuration_changed")
        self.assertEqual(self.entry.options["slicer_base_url"], "https://user-choice.invalid")

    async def test_unrelated_options_change_is_merged_at_completion(self):
        await self.prepare()
        self.entry.options["printer_name"] = "user-new-name"
        options = await self.session.async_connection_options(self.entry)
        self.assertEqual(options["printer_name"], "user-new-name")
        self.assertEqual(options["slicer_api_secret"], KEY)

    async def test_user_connection_change_after_probe_is_preserved(self):
        await self.prepare()
        self.entry.options["slicer_api_secret"] = "Y" * 64
        self.assertIsNone(await self.session.async_connection_options(self.entry))
        self.assertEqual(self.entry.options["slicer_api_secret"], "Y" * 64)

    async def test_replaced_handoff_after_probe_is_not_applied(self):
        await self.prepare()
        put(self.directory, wire(transfer_id="c" * 32))
        self.assertIsNone(await self.session.async_connection_options(self.entry))
        self.assertEqual(self.entry.options, self.before)

    async def test_another_entry_cannot_receive_offer(self):
        await self.prepare()
        other = SimpleNamespace(entry_id="different", options={}, data={})
        self.assertIsNone(await self.session.async_connection_options(other))
        self.assertEqual(other.options, {})

    async def test_finish_without_verification_never_reads_or_applies(self):
        self.assertIsNone(await self.session.async_connection_options(self.entry))
        self.assertEqual(self.hass.threads, [])

    async def test_parallel_install_is_rejected_during_verification(self):
        self.block_probe = True
        task = asyncio.create_task(self.prepare())
        await asyncio.wait_for(self.probe_started.wait(), 1)
        result = await self.session.async_run("install")
        self.assertEqual(result["error"], "installer_busy")
        self.assertEqual(self.host_calls, [])
        self.probe_release.set()
        self.assertTrue((await task)["ok"])

    async def test_other_mutation_invalidates_prepared_offer(self):
        await self.prepare()
        await self.session.async_run("initialize")
        self.assertIsNone(await self.session.async_connection_options(self.entry))
        self.assertEqual(self.host_calls, ["initialize"])

    async def test_endpoint_change_before_finalization_rejects_offer(self):
        await self.prepare()
        self.endpoint[0] = SimpleNamespace(host_id="c" * 32, server_uid=0,
            handoff_directory=str(self.directory), socket_directory="/different")
        self.assertIsNone(await self.session.async_connection_options(self.entry))
        self.assertEqual(self.session.snapshot()["result"]["error"], "endpoint_changed")

    async def test_close_invalidates_offer_without_deleting_source(self):
        await self.prepare()
        await self.session.async_close()
        self.assertIsNone(await self.session.async_connection_options(self.entry))
        self.assertEqual(self.path.read_bytes(), wire())

    async def test_arbitrary_probe_error_is_not_exposed(self):
        self.probe_error = "private details " + KEY
        result = await self.prepare()
        self.assertNotIn(KEY, json.dumps(result))
        self.assertFalse(result["ok"])


@unittest.skipUnless(sys.platform == "linux" and hasattr(os, "geteuid") and os.geteuid() == 0,
                     "isolated Linux root publisher fixture")
class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "handoff"
        self.root.mkdir(mode=0o700)
    def publish(self, **changes):
        args = {"host_id": HOST, "principal": "ha", "transfer_id": TRANSFER, "base_url": URL,
                "api_secret": KEY, "recipient_uid": 0, "recipient_gid": os.getegid()}
        args.update(changes)
        return handoff.publish_connection_offer(self.root, **args)
    def test_atomic_publication_is_owner_bound_and_secret_free(self):
        result = self.publish()
        self.assertEqual(result, {"published": True, "already_present": False})
        path = self.root / handoff.CONNECTION_FILE
        self.assertEqual(path.stat().st_mode & 0o777, 0o400)
        self.assertEqual(path.stat().st_nlink, 1)
        self.assertEqual(path.read_bytes(), wire())
        self.assertNotIn(KEY, json.dumps(result))
    def test_identical_publication_is_idempotent(self):
        self.publish()
        before = (self.root / handoff.CONNECTION_FILE).stat()
        self.assertTrue(self.publish()["already_present"])
        after = (self.root / handoff.CONNECTION_FILE).stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
    def test_new_offer_does_not_overwrite_existing_offer(self):
        self.publish()
        with self.assertRaisesRegex(handoff.ConnectionHandoffError, "connection_handoff_occupied"):
            self.publish(transfer_id="d" * 32)
        self.assertEqual((self.root / handoff.CONNECTION_FILE).read_bytes(), wire())
    def test_invalid_input_does_not_publish_any_file(self):
        with self.assertRaises(handoff.ConnectionHandoffError):
            self.publish(base_url="http://localhost")
        self.assertEqual(list(self.root.iterdir()), [])


class ConnectionFlowTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = ConnectionAsyncTests.asyncSetUp
    asyncTearDown = ConnectionAsyncTests.asyncTearDown
    prepare = ConnectionAsyncTests.prepare

    def flow(self):
        source = ast.parse((COMP / "slicer_installer_flow.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "InstallerOptionsFlowMixin")
        choices = next(ast.literal_eval(n.value) for n in source.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "CHOICES" for t in n.targets))
        namespace = {"ACTIONS": runtime.ACTIONS, "MUTATION_ACTIONS": runtime.MUTATION_ACTIONS,
                     "CHOICES": choices, "get_installer_session": lambda *_: self.session,
                     "vol": SimpleNamespace(Schema=lambda value: value, Required=lambda key, **kwargs: key),
                     "selector": SimpleNamespace(SelectSelector=lambda value: value,
                         SelectSelectorConfig=lambda **kwargs: kwargs,
                         SelectSelectorMode=SimpleNamespace(DROPDOWN="dropdown"))}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "isolated_native_flow", "exec"), namespace)
        class Flow(namespace["InstallerOptionsFlowMixin"]):
            def async_show_form(self, **kwargs): return {"type": "form", **kwargs}
            def async_abort(self, **kwargs): return {"type": "abort", **kwargs}
            def async_show_progress(self, **kwargs): return {"type": "progress", **kwargs}
            def async_show_progress_done(self, **kwargs): return {"type": "progress_done", **kwargs}
            def async_create_entry(self, **kwargs): return {"type": "native_options_completion", **kwargs}
        flow = Flow()
        flow.hass = self.hass
        flow.config_entry = self.entry
        flow._installer_session = self.session
        return flow

    async def test_connection_action_requires_native_confirmation(self):
        flow = self.flow()
        answer = await flow.async_step_installer_action({"operation": "configure_connection"})
        self.assertEqual(answer["step_id"], "installer_confirm")
        self.assertEqual(self.probe_calls, [])
        self.assertEqual(self.entry.options, self.before)

    async def test_unconfirmed_connection_action_never_reads_secret(self):
        flow = self.flow()
        flow._installer_action = "configure_connection"
        await flow.async_step_installer_confirm({"confirm": False})
        self.assertEqual(self.probe_calls, [])
        self.assertEqual(self.host_calls, [])

    async def test_progress_task_result_has_no_secret_and_finishes_via_native_flow(self):
        flow = self.flow()
        flow._installer_action = "configure_connection"
        answer = await flow.async_step_installer_confirm({"confirm": True})
        self.assertEqual(answer["type"], "progress")
        result = await flow._installer_task
        self.assertNotIn(KEY, json.dumps(result))
        answer = await flow.async_step_installer_progress()
        self.assertEqual(answer["next_step_id"], "installer_connection_finish")
        answer = await flow.async_step_installer_connection_finish()
        self.assertEqual(answer["type"], "native_options_completion")
        self.assertEqual(answer["data"]["slicer_api_secret"], KEY)
        self.assertEqual(self.entry.options, self.before)
        self.assertTrue(self.path.exists())

    async def test_browser_supplied_address_and_secret_are_ignored(self):
        await self.prepare()
        flow = self.flow()
        result = await flow.async_step_installer_connection_finish(
            {"slicer_base_url": "https://attacker.invalid", "slicer_api_secret": "Z" * 64})
        self.assertEqual(result["data"]["slicer_base_url"], URL)
        self.assertEqual(result["data"]["slicer_api_secret"], KEY)

    async def test_unverified_finish_does_not_complete_options(self):
        result = await self.flow().async_step_installer_connection_finish()
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "installer_action")
        self.assertEqual(self.entry.options, self.before)



if __name__ == "__main__":
    unittest.main()
