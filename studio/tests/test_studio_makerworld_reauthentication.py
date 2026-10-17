"""Isolated production-flow tests; synthetic auth/responses, no account or printer I/O.

Run with pytest or ``python tests/test_studio_makerworld_reauthentication.py``.
Home Assistant adapters are stubbed. When installed, real voluptuous validates
that the official options-flow initial form accepts the dedicated routing flag.
"""
from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

try:
    import voluptuous as REAL_VOL
except ImportError:
    REAL_VOL = None

COMPONENT = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio"
PREFIX = "isolated_studio_makerworld_reauth"


class Marker:
    def __init__(self, schema, **kwargs):
        self.schema = schema
        self.default = kwargs.get("default")


class Schema:
    def __init__(self, schema):
        self.schema = schema


class Selector:
    def __init__(self, config):
        self.config = config

    def __call__(self, value):
        return value


class Flow:
    def __init_subclass__(cls, **_kwargs):
        return super().__init_subclass__()

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}


class AuthError(RuntimeError):
    pass


class CodeRequired(AuthError):
    pass


class MakerWorldError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tokens:
    access_token: str = "SYNTHETIC_NEW_ACCESS"
    refresh_token: str = "SYNTHETIC_NEW_REFRESH"
    uid: str = "synthetic-uid"


def module(name, **values):
    result = ModuleType(name)
    result.__dict__.update(values)
    return result


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


class IsolatedModules(unittest.TestCase):
    def setUp(self):
        constants = {}
        for filename in ("config_flow.py", "makerworld_views.py"):
            tree = ast.parse((COMPONENT / filename).read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "const":
                    for item in node.names:
                        constants[item.name] = item.name.removeprefix("CONF_").lower()
        constants.update(DOMAIN="ultimate_3d_studio", VERSION="synthetic-test", API_BASE="/api/ultimate_3d_studio/v1",
                         REGION_GLOBAL="global", REGION_CHINA="china", DEFAULT_CLOUD_PROFILE_SYNC=False,
                         DEFAULT_TLS_INSECURE=False, DEFAULT_PRINTER_NAME="Synthetic printer", DEFAULT_INSTANCE_NAME="Synthetic studio")
        package = module(PREFIX)
        package.__path__ = [str(COMPONENT)]
        config_entries = module("homeassistant.config_entries", ConfigFlow=Flow, OptionsFlow=Flow, ConfigFlowResult=dict)
        selectors = module("homeassistant.helpers.selector", TextSelector=Selector, SelectSelector=Selector,
                           TextSelectorConfig=lambda **kwargs: kwargs, SelectSelectorConfig=lambda **kwargs: kwargs,
                           TextSelectorType=SimpleNamespace(EMAIL="email", PASSWORD="password", TEXT="text", URL="url"),
                           SelectSelectorMode=SimpleNamespace(DROPDOWN="dropdown"))
        stubs = {
            PREFIX: package,
            "homeassistant": module("homeassistant", config_entries=config_entries),
            "homeassistant.config_entries": config_entries,
            "homeassistant.const": module("homeassistant.const", CONF_PASSWORD="password"),
            "homeassistant.core": module("homeassistant.core", callback=lambda function: function, HomeAssistant=object),
            "homeassistant.helpers": module("homeassistant.helpers", selector=selectors),
            "homeassistant.helpers.selector": selectors,
            "homeassistant.helpers.aiohttp_client": module("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda _hass: None),
            "homeassistant.components": module("homeassistant.components"),
            "homeassistant.components.http": module("homeassistant.components.http", HomeAssistantView=object),
            PREFIX + ".const": module(PREFIX + ".const", **constants),
            PREFIX + ".bambu_cloud_auth": module(PREFIX + ".bambu_cloud_auth", BambuCloudAuth=Mock(), BambuCloudAuthError=AuthError,
                                                  BambuCloudTokens=Tokens, VerificationCodeRequired=CodeRequired),
            PREFIX + ".slicer_connection_probe": module(PREFIX + ".slicer_connection_probe", SlicerConnectionProbeError=RuntimeError,
                                                         async_probe_slicer_connection=AsyncMock()),
            PREFIX + ".slicer_connection_settings": module(PREFIX + ".slicer_connection_settings", SlicerConnectionSettingsError=RuntimeError,
                                                            normalize_slicer_base_url=lambda value: value, validate_slicer_api_secret=lambda value: None),
            PREFIX + ".slicer_installer_flow": module(PREFIX + ".slicer_installer_flow", CONF_INSTALLER_SETUP="slicer_installer_setup",
                                                       InstallerOptionsFlowMixin=type("InstallerOptionsFlowMixin", (), {})),
            PREFIX + ".slicer_installation_flow": module(PREFIX + ".slicer_installation_flow", SlicerInstallationFlowMixin=type("SlicerInstallationFlowMixin", (), {})),
            PREFIX + ".makerworld_runtime": module(PREFIX + ".makerworld_runtime", MakerWorldError=MakerWorldError, get_makerworld_runtime=Mock()),
            PREFIX + ".gallery_repository": module(PREFIX + ".gallery_repository", StudioGalleryRepository=type("StudioGalleryRepository", (), {})),
            PREFIX + ".gallery_storage_paths": module(PREFIX + ".gallery_storage_paths", is_same_studio_storage_path=Mock(), studio_gallery_root=Mock()),
            PREFIX + ".geometry_export": module(PREFIX + ".geometry_export", export_binary_stl=Mock()),
            PREFIX + ".makerworld_detail": module(PREFIX + ".makerworld_detail", async_load_detail=AsyncMock()),
            PREFIX + ".makerworld_download": module(PREFIX + ".makerworld_download", async_download_instance=AsyncMock()),
            PREFIX + ".rich_text": module(PREFIX + ".rich_text", readable_rich_text=lambda value: value, safe_rich_html=lambda value: value),
        }
        if REAL_VOL is None:
            stubs["voluptuous"] = module("voluptuous", Schema=Schema, Required=Marker, Optional=Marker)
        self.modules_patch = patch.dict(sys.modules, stubs)
        self.modules_patch.start()
        self.addCleanup(self.modules_patch.stop)
        self.flow_module = load(PREFIX + ".config_flow", COMPONENT / "config_flow.py")
        self.transfer = load(PREFIX + ".makerworld_transfer", COMPONENT / "makerworld_transfer.py")
        self.views = load(PREFIX + ".makerworld_views", COMPONENT / "makerworld_views.py")
        self.constants = constants

    def flow(self, *, options=None, data=None):
        result = self.flow_module.Ultimate3DStudioOptionsFlow()
        result.hass = SimpleNamespace()
        result.config_entry = SimpleNamespace(options=deepcopy(options or {}), data=deepcopy(data or {}))
        return result

    def auth(self, *, password=None, code=None):
        client = SimpleNamespace(async_login_password=AsyncMock(return_value=Tokens()), async_login_code=AsyncMock(return_value=Tokens()))
        if password is not None:
            client.async_login_password.side_effect = password
        if code is not None:
            client.async_login_code.side_effect = code
        self.flow_module.BambuCloudAuth = Mock(return_value=client)
        return client

    def input(self, **kwargs):
        return {"cloud_email": "  synthetic@example.invalid  ", "password": "SYNTHETIC_PASSWORD", "cloud_region": "global", **kwargs}

    def invoke(self, awaitable):
        return asyncio.run(awaitable)


class TestMakerWorldReauthenticationFlow(IsolatedModules):
    def test_explicit_initial_route_opens_password_form_without_auth(self):
        flow = self.flow(options={"cloud_email": "synthetic@example.invalid", "cloud_region": "china"})
        client = self.auth()
        original = deepcopy(flow.config_entry.options)
        result = self.invoke(flow.async_step_init({"cloud_reauthenticate": True}))
        self.assertEqual((result["type"], result["step_id"]), ("form", "cloud_reauthenticate"))
        self.assertEqual(flow.config_entry.options, original)
        client.async_login_password.assert_not_called()
        self.assertNotIn("SYNTHETIC_PASSWORD", repr(result))

    @unittest.skipIf(REAL_VOL is None, "real voluptuous is not installed in this isolated runtime")
    def test_real_init_schema_accepts_reauth_flag_and_rejects_arbitrary_extras(self):
        flow = self.flow()
        initial = self.invoke(flow.async_step_init())
        validated = initial["data_schema"]({"cloud_reauthenticate": True})
        self.assertIs(validated["cloud_reauthenticate"], True)
        self.assertNotIn("password", validated)
        self.assertNotIn("slicer_api_secret", validated)
        self.assertNotIn("access_code", validated)
        with self.assertRaises(REAL_VOL.Invalid):
            initial["data_schema"]({"unknown_reauth_extra": True})
        client = self.auth()
        routed = self.invoke(flow.async_step_init(validated))
        self.assertEqual(routed["step_id"], "cloud_reauthenticate")
        client.async_login_password.assert_not_called()

    def test_password_success_changes_only_auth_and_retains_disabled_profile_sync(self):
        original = {"cloud_profile_sync": False, "cloud_access_token": "SYNTHETIC_OLD_ACCESS", "cloud_refresh_token": "SYNTHETIC_OLD_REFRESH",
                    "cloud_uid": "old-uid", "cloud_email": "old@example.invalid", "cloud_region": "china", "cloud_enabled": True,
                    "lan_enabled": True, "host": "synthetic-host.invalid", "slicer_api_secret": "SYNTHETIC_SLICER_SECRET",
                    "installer": {"state": "preserved"}}
        flow = self.flow(options=original)
        client = self.auth()
        result = self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        self.assertEqual(result["type"], "create_entry")
        expected = {**original, "cloud_email": "synthetic@example.invalid", "cloud_region": "global",
                    "cloud_access_token": Tokens().access_token, "cloud_refresh_token": Tokens().refresh_token, "cloud_uid": Tokens().uid}
        self.assertEqual(result["data"], expected)
        self.assertEqual(flow.config_entry.options, original)
        client.async_login_password.assert_awaited_once_with("synthetic@example.invalid", "SYNTHETIC_PASSWORD")
        client.async_login_code.assert_not_called()
        self.assertNotIn("SYNTHETIC_PASSWORD", repr(result) + repr(vars(flow)))

    def test_password_success_preserves_profile_sync_in_entry_data(self):
        flow = self.flow(data={"cloud_profile_sync": False}, options={"lan_enabled": True})
        self.auth()
        result = self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        self.assertIs(result["data"]["cloud_profile_sync"], False)
        self.assertIs(result["data"]["lan_enabled"], True)

    def test_code_challenge_keeps_credentials_ephemeral_and_commits_after_code_only(self):
        original = {"cloud_profile_sync": False, "cloud_access_token": "SYNTHETIC_OLD", "unrelated": "preserve"}
        flow = self.flow(options=original)
        client = self.auth(password=CodeRequired("synthetic verification challenge"))
        challenge = self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        self.assertEqual(challenge["step_id"], "cloud_code")
        self.assertEqual(flow.config_entry.options, original)
        self.assertNotIn("SYNTHETIC_PASSWORD", repr(challenge) + repr(vars(flow)))
        self.assertNotIn("password", flow._pending_options)
        result = self.invoke(flow.async_step_cloud_code({"verification_code": " SYNTHETIC_CODE "}))
        self.assertEqual(result["type"], "create_entry")
        self.assertIs(result["data"]["cloud_profile_sync"], False)
        self.assertEqual(result["data"]["unrelated"], "preserve")
        self.assertEqual(flow.config_entry.options, original)
        client.async_login_code.assert_awaited_once_with("synthetic@example.invalid", "SYNTHETIC_CODE")
        self.assertIsNone(flow._pending_options)
        self.assertEqual(flow._pending_email, "")
        self.assertNotIn("SYNTHETIC_CODE", repr(result) + repr(vars(flow)))

    def test_invalid_code_preserves_challenge_and_old_persisted_options(self):
        flow = self.flow(options={"cloud_access_token": "SYNTHETIC_OLD", "cloud_profile_sync": False})
        original = deepcopy(flow.config_entry.options)
        self.auth(password=CodeRequired(), code=AuthError("synthetic rejection"))
        self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        with self.assertLogs(self.flow_module.__name__, level="ERROR"):
            result = self.invoke(flow.async_step_cloud_code({"verification_code": "SYNTHETIC_BAD_CODE"}))
        self.assertEqual(result["errors"], {"base": "invalid_auth"})
        self.assertEqual(result["step_id"], "cloud_code")
        self.assertIsNotNone(flow._pending_options)
        self.assertEqual(flow.config_entry.options, original)
        self.assertNotIn("SYNTHETIC_BAD_CODE", repr(result) + repr(vars(flow)))

    def test_invalid_password_does_not_commit_or_echo_provider_error(self):
        flow = self.flow(options={"cloud_access_token": "SYNTHETIC_OLD"})
        self.auth(password=AuthError("SYNTHETIC_PROVIDER_BODY"))
        result = self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        self.assertEqual(result["errors"], {"base": "invalid_auth"})
        self.assertEqual(flow.config_entry.options, {"cloud_access_token": "SYNTHETIC_OLD"})
        self.assertNotIn("SYNTHETIC_PROVIDER_BODY", repr(result))
        self.assertNotIn("SYNTHETIC_PASSWORD", repr(result) + repr(vars(flow)))

    def test_connection_failure_does_not_persist_attempted_credentials(self):
        flow = self.flow(options={"unrelated": "preserve"})
        self.auth(password=RuntimeError("SYNTHETIC_PRIVATE_DIAGNOSTIC"))
        result = self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        self.assertEqual(result["errors"], {"base": "cannot_connect"})
        self.assertEqual(flow.config_entry.options, {"unrelated": "preserve"})
        self.assertNotIn("SYNTHETIC_PRIVATE_DIAGNOSTIC", repr(result))

    def test_invalid_password_form_never_calls_provider(self):
        invalid = [{"cloud_email": ""}, {"password": ""}, {"password": None}, {"cloud_email": ["invalid"]},
                   {"cloud_region": "unknown"}, {"cloud_region": {"invalid": "object"}}]
        for replacement in invalid:
            with self.subTest(replacement=replacement):
                flow = self.flow(options={"unrelated": "preserve"})
                client = self.auth()
                result = self.invoke(flow.async_step_cloud_reauthenticate(self.input(**replacement)))
                self.assertEqual(result["errors"], {"base": "invalid_auth"})
                client.async_login_password.assert_not_called()
                self.assertEqual(flow.config_entry.options, {"unrelated": "preserve"})

    def test_cancelled_password_request_propagates_and_retains_existing_options(self):
        flow = self.flow(options={"cloud_access_token": "SYNTHETIC_OLD", "unrelated": "preserve"})
        self.auth(password=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        self.assertEqual(flow.config_entry.options, {"cloud_access_token": "SYNTHETIC_OLD", "unrelated": "preserve"})
        self.assertIsNone(flow._pending_options)
        self.assertNotIn("SYNTHETIC_PASSWORD", repr(vars(flow)))

    def test_abandoned_code_challenge_leaves_persisted_options_unchanged(self):
        original = {"cloud_access_token": "SYNTHETIC_OLD", "unrelated": "preserve"}
        flow = self.flow(options=original)
        self.auth(password=CodeRequired())
        self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        # HA cancellation discards the in-memory flow; only create_entry commits.
        self.assertEqual(flow.config_entry.options, original)
        self.assertNotIn("password", flow._pending_options)
        self.assertNotIn("verification_code", flow._pending_options)

    def test_new_password_form_invalidates_old_code_challenge(self):
        flow = self.flow()
        self.auth(password=CodeRequired())
        self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        self.assertIsNotNone(flow._pending_options)
        self.invoke(flow.async_step_cloud_reauthenticate())
        expired = self.invoke(flow.async_step_cloud_code({"verification_code": "SYNTHETIC_CODE"}))
        self.assertEqual(expired, {"type": "abort", "reason": "cloud_login_expired"})

    def test_password_wait_preserves_concurrently_saved_lan_and_slicer_options(self):
        flow = self.flow(options={"cloud_profile_sync": False, "slicer_base_url": "https://old.invalid", "lan_enabled": False})
        client = self.auth()
        async def complete_after_option_update(_email, _password):
            flow.config_entry.options = {
                **flow.config_entry.options, "slicer_base_url": "https://new.invalid",
                "slicer_api_secret": "SYNTHETIC_NEW_SLICER_SECRET", "lan_enabled": True,
                "cloud_profile_sync": True, "another_option": {"preserved": "latest"},
            }
            return Tokens()
        client.async_login_password.side_effect = complete_after_option_update
        result = self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        for key in ("slicer_base_url", "slicer_api_secret", "lan_enabled", "cloud_profile_sync", "another_option"):
            self.assertEqual(result["data"][key], flow.config_entry.options[key])
        self.assertEqual(result["data"]["cloud_access_token"], Tokens().access_token)

    def test_code_pause_preserves_concurrently_saved_lan_and_slicer_options(self):
        flow = self.flow(options={"cloud_profile_sync": True, "slicer_base_url": "https://old.invalid", "lan_enabled": False})
        self.auth(password=CodeRequired())
        self.invoke(flow.async_step_cloud_reauthenticate(self.input()))
        flow.config_entry.options = {
            **flow.config_entry.options, "slicer_base_url": "https://new.invalid",
            "slicer_api_secret": "SYNTHETIC_NEW_SLICER_SECRET", "lan_enabled": True,
            "cloud_profile_sync": False, "another_option": {"preserved": "latest"},
        }
        latest = deepcopy(flow.config_entry.options)
        result = self.invoke(flow.async_step_cloud_code({"verification_code": "SYNTHETIC_CODE"}))
        for key in ("slicer_base_url", "slicer_api_secret", "lan_enabled", "cloud_profile_sync", "another_option"):
            self.assertEqual(result["data"][key], latest[key])
        self.assertEqual(result["data"]["cloud_access_token"], Tokens().access_token)
        self.assertEqual(flow.config_entry.options, latest)

    def test_normal_login_token_helper_keeps_previous_profile_sync_semantics(self):
        result = self.flow_module.Ultimate3DStudioOptionsFlow._with_tokens({"cloud_profile_sync": False}, Tokens())
        self.assertIs(result["cloud_profile_sync"], True)


class Response:
    def __init__(self, status=200, body=b""):
        self.status = status
        self.body = body
        self.content_length = len(body)
        self.content = self
        self.reads = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def iter_chunked(self, _size):
        self.reads += 1
        yield self.body


class TestMakerWorldReauthenticationClassification(IsolatedModules):
    def runtime(self, responses, *, account_changed=False):
        calls = []
        def get(url, **kwargs):
            calls.append((str(url), kwargs))
            return responses[len(calls) - 1]
        runtime = SimpleNamespace(hass=object(), _resolve_model_id=AsyncMock(return_value="US3575d30b9f913b"),
                                  _headers=lambda _account: {"Authorization": "Bearer SYNTHETIC_PRIVATE", "User-Agent": "synthetic"},
                                  _check_account=Mock(side_effect=MakerWorldError("account changed") if account_changed else None))
        self.transfer.async_get_clientsession = lambda _hass: SimpleNamespace(get=get)
        account = SimpleNamespace(entry_id="synthetic-entry-id", api_base="https://api.bambulab.com/v1")
        return runtime, account, calls

    def download(self, runtime, account):
        return self.transfer.download_signed_profile(runtime, account, "3376079", "1034162562", "US3575d30b9f913b")

    def body(self, response):
        return json.loads(response.body)

    def test_manifest_401_binds_exact_account_and_returns_safe_popup_details(self):
        first = Response(401, b"SYNTHETIC_PRIVATE_BODY")
        runtime, account, calls = self.runtime([first])
        with self.assertRaises(self.transfer.MakerWorldTransferError) as context:
            self.invoke(self.download(runtime, account))
        error = context.exception
        self.assertEqual(error.config_entry_id, account.entry_id)
        self.assertEqual(error.upstream_status, 401)
        self.assertEqual(first.reads, 0)
        self.assertEqual(len(calls), 1)
        response = self.views._transfer_error(error)
        result = self.body(response)
        self.assertEqual(response.status, 502)
        self.assertEqual(result["error"]["code"], "makerworld_account_unauthorized")
        self.assertEqual(result["error"]["details"], {"upstream_status": 401, "config_entry_id": account.entry_id})
        self.assertNotIn("SYNTHETIC_PRIVATE", repr(result))

    def test_signed_storage_401_does_not_offer_account_login_or_expose_binding(self):
        runtime, account, calls = self.runtime([Response(body=b'{"url":"https://makerworld.bblmw.com/synthetic.3mf?sig=SYNTHETIC_PRIVATE"}'), Response(401)])
        with self.assertRaises(self.transfer.MakerWorldTransferError) as context:
            self.invoke(self.download(runtime, account))
        error = context.exception
        self.assertEqual(error.code, "makerworld_signed_download_denied")
        self.assertFalse(hasattr(error, "config_entry_id"))
        result = self.body(self.views._transfer_error(error))
        self.assertEqual(result["error"]["code"], "makerworld_download_failed")
        self.assertNotIn("details", result["error"])
        self.assertEqual(len(calls), 2)
        self.assertNotIn("SYNTHETIC_PRIVATE", repr(result))

    def test_account_change_during_manifest_401_does_not_open_stale_account_login(self):
        runtime, account, _calls = self.runtime([Response(401)], account_changed=True)
        with self.assertRaisesRegex(MakerWorldError, "account changed") as context:
            self.invoke(self.download(runtime, account))
        result = self.body(self.views._transfer_error(context.exception))
        self.assertEqual(result["error"]["code"], "makerworld_download_failed")
        self.assertNotIn("details", result["error"])

    def test_incomplete_or_invalid_bindings_cannot_trigger_login(self):
        cases = [("", 401, "makerworld_account_unauthorized"), ("bad/id", 401, "makerworld_account_unauthorized"),
                 ("entry", 403, "makerworld_account_unauthorized"), ("entry", 401, "makerworld_signed_download_denied")]
        for entry, status, code in cases:
            with self.subTest(entry=entry, status=status, code=code):
                error = self.transfer.MakerWorldTransferError(code, "sanitized", upstream_status=status)
                error.config_entry_id = entry
                result = self.body(self.views._transfer_error(error))
                self.assertEqual(result["error"]["code"], "makerworld_download_failed")
                self.assertNotIn("details", result["error"])

    def test_other_manifest_denials_do_not_trigger_login(self):
        for status in (403, 404, 429, 500):
            with self.subTest(status=status):
                runtime, account, calls = self.runtime([Response(status)])
                with self.assertRaises(self.transfer.MakerWorldTransferError) as context:
                    self.invoke(self.download(runtime, account))
                error = context.exception
                self.assertFalse(hasattr(error, "config_entry_id"))
                result = self.body(self.views._transfer_error(error))
                self.assertNotIn("details", result["error"])
                self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
