"""OptionsFlow contract for configured slicer; mocks HA but never stores real tokens."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
import importlib.util
from pathlib import Path
import sys
import types
from types import SimpleNamespace

import pytest


COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"
)
DEMO_SECRET = "test-only-secret-" + "C" * 48


@pytest.fixture
def flow_module(monkeypatch):
    namespace = "studio_slicer_options_test"
    pkg = types.ModuleType(namespace)
    pkg.__path__ = [str(COMPONENT)]
    monkeypatch.setitem(sys.modules, namespace, pkg)

    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = lambda fields: fields
    voluptuous.Required = lambda key, **kwargs: key
    voluptuous.Optional = lambda key, **kwargs: key
    monkeypatch.setitem(sys.modules, "voluptuous", voluptuous)

    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    entries = types.ModuleType("homeassistant.config_entries")
    core = types.ModuleType("homeassistant.core")
    const = types.ModuleType("homeassistant.const")
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    selectors = types.ModuleType("homeassistant.helpers.selector")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    # Explicit HA request boundary. No authenticated actor is fabricated.
    http_context = types.ModuleType("homeassistant.helpers.http")
    http_context.KEY_AUTHENTICATED = "ha_authenticated"
    http_context.current_request = ContextVar("test_ha_current_request", default=None)

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

    class OptionsFlow:
        config_entry = None

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_show_menu(self, **kwargs):
            return {"type": "menu", **kwargs}

        def async_create_entry(self, *, title, data):
            return {"type": "entry", "title": title, "data": data}

        def async_abort(self, *, reason):
            return {"type": "abort", "reason": reason}

    entries.ConfigFlow = ConfigFlow
    entries.ConfigFlowResult = dict
    entries.OptionsFlow = OptionsFlow
    core.callback = lambda fn: fn
    const.CONF_PASSWORD = "password"
    const.Platform = SimpleNamespace(
        SENSOR="sensor", BINARY_SENSOR="binary_sensor", BUTTON="button", CAMERA="camera",
    )
    selectors.TextSelectorConfig = lambda **kw: kw
    selectors.TextSelector = lambda config: ("text", config)
    selectors.SelectSelectorConfig = lambda **kw: kw
    selectors.SelectSelector = lambda config: ("select", config)
    selectors.TextSelectorType = SimpleNamespace(
        PASSWORD="password", EMAIL="email", URL="url", TEXT="text",
    )
    selectors.SelectSelectorMode = SimpleNamespace(DROPDOWN="dropdown")
    aiohttp_client.async_get_clientsession = lambda hass: None

    for name, obj in (
        ("homeassistant", ha),
        ("homeassistant.config_entries", entries),
        ("homeassistant.core", core),
        ("homeassistant.const", const),
        ("homeassistant.helpers", helpers),
        ("homeassistant.helpers.selector", selectors),
        ("homeassistant.helpers.aiohttp_client", aiohttp_client),
        ("homeassistant.helpers.http", http_context),
    ):
        monkeypatch.setitem(sys.modules, name, obj)
    ha.config_entries = entries

    cloud = types.ModuleType(namespace + ".bambu_cloud_auth")
    cloud.BambuCloudAuth = object
    cloud.BambuCloudAuthError = type("BambuCloudAuthError", (RuntimeError,), {})
    cloud.BambuCloudTokens = object
    cloud.VerificationCodeRequired = type(
        "VerificationCodeRequired", (RuntimeError,), {},
    )
    monkeypatch.setitem(sys.modules, namespace + ".bambu_cloud_auth", cloud)

    def load(name):
        full = namespace + "." + name
        spec = importlib.util.spec_from_file_location(full, COMPONENT / (name + ".py"))
        assert spec and spec.loader
        obj = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, full, obj)
        spec.loader.exec_module(obj)
        return obj

    load("const")
    load("slicer_connection_settings")
    load("slicer_connection_probe")
    return load("config_flow")


def _flow(module, current=None):
    flow = module.Ultimate3DStudioOptionsFlow()
    flow.config_entry = SimpleNamespace(data={}, options=current or {})
    return flow


def test_slicer_options_preserve_saved_secret_without_refilling_the_password_field(flow_module):
    current = {
        "slicer_enabled": True,
        "slicer_base_url": "https://slicer.example.org:8443",
        "slicer_api_secret": DEMO_SECRET,
    }
    flow = _flow(flow_module, current)
    form = asyncio.run(flow.async_step_advanced())
    assert form["type"] == "form"
    assert form["description_placeholders"]["slicer_secret_status"] == "vorhanden"
    assert DEMO_SECRET not in str(form)

    result = asyncio.run(flow.async_step_init({
        "slicer_enabled": True,
        "slicer_base_url": "https://SLICER.example.org:8443/",
    }))
    assert result["type"] == "entry"
    assert result["data"]["slicer_api_secret"] == DEMO_SECRET
    assert result["data"]["slicer_base_url"] == "https://slicer.example.org:8443"


def test_disabled_slicer_does_not_require_address_or_secret(flow_module):
    result = asyncio.run(_flow(flow_module).async_step_init({"slicer_enabled": False}))
    assert result["type"] == "entry"
    assert result["data"]["slicer_enabled"] is False


@pytest.mark.parametrize(
    ("url", "secret", "field", "error"),
    [
        ("http://remote.example.org", DEMO_SECRET, "slicer_base_url", "slicer_https_required"),
        ("https://slicer.example.org", "", "slicer_api_secret", "invalid_slicer_secret"),
        ("https://user:pass@slicer.example.org", DEMO_SECRET, "slicer_base_url", "invalid_slicer_url"),
    ],
)
def test_slicer_flow_rejects_invalid_connection_options(flow_module, url, secret, field, error):
    result = asyncio.run(_flow(flow_module).async_step_init({
        "slicer_enabled": True,
        "slicer_base_url": url,
        "slicer_api_secret": secret,
    }))
    assert result["type"] == "form"
    assert result["errors"][field] == error
    assert DEMO_SECRET not in str(result)


def test_secret_can_be_replaced_without_revealing_old_value(flow_module):
    current = {
        "slicer_enabled": True,
        "slicer_base_url": "https://slicer.example.org",
        "slicer_api_secret": DEMO_SECRET,
    }
    changed = "test-only-rotated-" + "D" * 48
    result = asyncio.run(_flow(flow_module, current).async_step_init({
        "slicer_enabled": True,
        "slicer_base_url": current["slicer_base_url"],
        "slicer_api_secret": changed,
    }))
    assert result["type"] == "entry"
    assert result["data"]["slicer_api_secret"] == changed
    assert DEMO_SECRET not in str(result)


def test_slicer_server_update_preserves_existing_lan_and_cloud_credentials(flow_module):
    lan_secret = "synthetic-lan-credential-unique"
    cloud_token = "synthetic-cloud-token-only-for-tests"
    cloud_refresh = "synthetic-cloud-refresh-only-for-tests"
    current = {
        "lan_enabled": True,
        "printer_name": "Existing A1",
        "host": "192.0.2.10",
        "serial": "synthetic-printer-id",
        "access_code": lan_secret,
        "tls_insecure": False,
        "cloud_enabled": True,
        "cloud_profile_sync": False,
        "cloud_region": "global",
        "cloud_email": "user@example.invalid",
        "cloud_access_token": cloud_token,
        "cloud_refresh_token": cloud_refresh,
        "cloud_uid": "synthetic-user",
        "slicer_enabled": False,
    }
    flow = _flow(flow_module, current)
    form = asyncio.run(flow.async_step_advanced())
    assert form["type"] == "form"
    assert form["description_placeholders"]["lan_code_status"] == "vorhanden"
    assert lan_secret not in str(form)
    assert cloud_token not in str(form)
    assert cloud_refresh not in str(form)
    assert form["data_schema"]["access_code"][1]["type"] == "password"

    result = asyncio.run(flow.async_step_init({
        "slicer_enabled": True,
        "slicer_base_url": "https://slicer.example.org:8443",
        "slicer_api_secret": DEMO_SECRET,
    }))
    assert result["type"] == "entry"
    data = result["data"]
    assert data["lan_enabled"] is True
    assert data["printer_name"] == "Existing A1"
    assert data["host"] == "192.0.2.10"
    assert data["serial"] == "synthetic-printer-id"
    assert data["access_code"] == lan_secret
    assert data["tls_insecure"] is False
    assert data["cloud_enabled"] is True
    assert data["cloud_profile_sync"] is False
    assert data["cloud_region"] == "global"
    assert data["cloud_email"] == "user@example.invalid"
    assert data["cloud_access_token"] == cloud_token
    assert data["cloud_refresh_token"] == cloud_refresh
    assert data["slicer_api_secret"] == DEMO_SECRET


def test_lan_code_rotation_requires_only_new_value_not_reentry_of_old_password(flow_module):
    old_code = "previous-synthetic-lan-code"
    new_code = "replacement-synthetic-lan-code"
    current = {
        "lan_enabled": True,
        "host": "192.0.2.11",
        "serial": "synthetic-printer",
        "access_code": old_code,
        "slicer_enabled": True,
        "slicer_base_url": "https://slicer.example.org",
        "slicer_api_secret": DEMO_SECRET,
    }
    flow = _flow(flow_module, current)
    edited = asyncio.run(flow.async_step_init({"access_code": new_code}))
    assert edited["type"] == "entry"
    assert edited["data"]["access_code"] == new_code
    assert edited["data"]["slicer_api_secret"] == DEMO_SECRET
    assert edited["data"]["lan_enabled"] is True


def _probe_session(status=200):
    import json

    class Content:
        async def read(self, limit):
            return json.dumps({
                "api_version": 2,
                "version": "0.1.0-alpha5",
                "capabilities": {"job_cancellation": True},
            }).encode("utf-8")[:limit]

    class Response:
        def __init__(self):
            self.status = status
            self.content = Content()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()

    return Session()


def test_connection_probe_shows_status_without_saving_options(flow_module):
    session = _probe_session()
    flow_module.async_get_clientsession = lambda _hass: session
    flow = _flow(flow_module)
    flow.hass = object()
    first = asyncio.run(flow.async_step_init({
        "slicer_enabled": True,
        "slicer_base_url": "https://slicer.example.invalid:8443",
        "slicer_api_secret": DEMO_SECRET,
        "slicer_connection_test": True,
    }))
    assert first["type"] == "form", "testing must never commit the secret"
    assert "bereit (Server 0.1.0-alpha5)" == first["description_placeholders"]["slicer_connection_status"]
    assert DEMO_SECRET not in str(first)
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == "https://slicer.example.invalid:8443/info.json"
    assert kwargs["headers"]["Authorization"] == "Bearer " + DEMO_SECRET
    assert kwargs["ssl"] is True and kwargs["allow_redirects"] is False

    saved = asyncio.run(flow.async_step_init({"slicer_enabled": True}))
    assert saved["type"] == "entry"
    assert saved["data"]["slicer_base_url"] == "https://slicer.example.invalid:8443"
    assert saved["data"]["slicer_api_secret"] == DEMO_SECRET
    assert "slicer_connection_test" not in saved["data"]


def test_connection_probe_auth_failure_is_not_saved_or_exposed(flow_module):
    session = _probe_session(status=401)
    flow_module.async_get_clientsession = lambda _hass: session
    flow = _flow(flow_module)
    flow.hass = object()
    result = asyncio.run(flow.async_step_init({
        "slicer_enabled": True,
        "slicer_base_url": "https://slicer.example.invalid",
        "slicer_api_secret": DEMO_SECRET,
        "slicer_connection_test": True,
    }))
    assert result["type"] == "form"
    assert result["errors"]["base"] == "slicer_auth_required"
    assert result["description_placeholders"]["slicer_connection_status"] == "fehlgeschlagen"
    assert DEMO_SECRET not in str(result)


def test_connection_probe_disabled_slicer_never_starts_request(flow_module):
    session = _probe_session()
    flow_module.async_get_clientsession = lambda _hass: session
    flow = _flow(flow_module)
    flow.hass = object()
    result = asyncio.run(flow.async_step_init({
        "slicer_enabled": False,
        "slicer_connection_test": True,
    }))
    assert result["type"] == "form"
    assert result["errors"]["base"] == "slicer_not_configured"
    assert session.calls == []


def test_native_installer_menu_does_not_use_runtime_or_expose_saved_secret(flow_module):
    current = {"slicer_enabled": True, "slicer_base_url": "https://slicer.example.org", "slicer_api_secret": DEMO_SECRET}
    flow = _flow(flow_module, current)
    flow.hass = object()  # Any runtime/config/Supervisor access would fail.
    result = asyncio.run(flow.async_step_init({"slicer_installer_setup": True}))
    assert result["type"] == "menu"
    assert result["menu_options"] == ["slicer_supervisor", "slicer_external", "slicer_host_legacy"]
    assert flow.config_entry.options == current
    assert DEMO_SECRET not in str(result)


def test_native_external_route_retains_the_existing_connection_form(flow_module):
    current = {"slicer_enabled": True, "slicer_base_url": "https://slicer.example.org", "slicer_api_secret": DEMO_SECRET}
    flow = _flow(flow_module, current)
    flow.hass = object()
    result = asyncio.run(flow.async_step_slicer_external())
    assert result["type"] == "menu" and result["step_id"] == "init"
    assert flow._current()["slicer_api_secret"] == DEMO_SECRET
    assert flow.config_entry.options == current
    assert DEMO_SECRET not in str(result)



def test_guided_menu_separates_printer_slicer_account_and_dashboard(flow_module):
    result = asyncio.run(_flow(flow_module).async_step_init())
    assert result['type'] == 'menu'
    assert result['menu_options'] == ['setup_printer','setup_slicer','setup_account','setup_dashboard','advanced']


def test_guided_printer_saves_lan_and_preserves_unrelated_connection(flow_module):
    flow = _flow(flow_module, {'slicer_api_secret':DEMO_SECRET,'cloud_access_token':'saved-cloud'})
    flow._guided_candidates = {}
    result = asyncio.run(flow.async_step_setup_printer({
        'lan_enabled':True,'host':'192.0.2.10','serial':'TEST_SERIAL',
        'access_code':'test-only-code','tls_insecure':False}))
    assert result['type'] == 'entry'
    assert result['data']['lan_enabled'] is True
    assert result['data']['slicer_api_secret'] == DEMO_SECRET
    assert result['data']['cloud_access_token'] == 'saved-cloud'


def test_guided_printer_missing_required_fields_cannot_finish(flow_module):
    flow = _flow(flow_module)
    flow._guided_candidates = {}
    result=asyncio.run(flow.async_step_setup_printer({'lan_enabled':True}))
    assert result['type']=='form'
    assert set(result['errors'])=={'host','serial','access_code'}


def test_guided_slicer_checks_and_saves_same_submission(flow_module,monkeypatch):
    module = sys.modules[flow_module.__package__+'.setup_flow']
    calls=[]
    async def probe(session,url,secret):
        calls.append((url,secret))
        return {'status':'ready'}
    monkeypatch.setattr(module,'async_probe_slicer_connection',probe)
    flow=_flow(flow_module,{'lan_enabled':True,'host':'192.0.2.10','serial':'TEST_SERIAL','access_code':'saved-code','slicer_api_secret':DEMO_SECRET})
    flow.hass=object()
    result=asyncio.run(flow.async_step_setup_slicer({'slicer_enabled':True,'slicer_base_url':'https://slicer.example.org','verify_connection':True}))
    assert result['type']=='entry'
    assert result['data']['lan_enabled'] is True
    assert result['data']['slicer_enabled'] is True
    assert calls==[('https://slicer.example.org',DEMO_SECRET)]


def test_guided_slicer_failure_keeps_form_and_hides_secret(flow_module,monkeypatch):
    module=sys.modules[flow_module.__package__+'.setup_flow']
    async def probe(*args):raise module.SlicerConnectionProbeError('slicer_unavailable')
    monkeypatch.setattr(module,'async_probe_slicer_connection',probe)
    flow=_flow(flow_module,{'slicer_api_secret':DEMO_SECRET})
    flow.hass=object()
    result=asyncio.run(flow.async_step_setup_slicer({'slicer_enabled':True,'slicer_base_url':'https://slicer.example.org'}))
    assert result['type']=='form' and result['errors']['base']=='slicer_unavailable'
    assert DEMO_SECRET not in str(result)


def test_guided_offline_slicer_can_be_saved_explicitly_without_network(flow_module,monkeypatch):
    module=sys.modules[flow_module.__package__+'.setup_flow']
    async def forbidden(*args):raise AssertionError('network forbidden')
    monkeypatch.setattr(module,'async_probe_slicer_connection',forbidden)
    result=asyncio.run(_flow(flow_module,{'slicer_api_secret':DEMO_SECRET}).async_step_setup_slicer({
        'slicer_enabled':True,'slicer_base_url':'https://slicer.example.org','verify_connection':False}))
    assert result['type']=='entry'


def test_guided_dashboard_preserves_other_saved_options(flow_module):
    result=asyncio.run(_flow(flow_module,{'access_code':'saved-code'}).async_step_setup_dashboard({'dashboard_auto':True}))
    assert result['data']['access_code']=='saved-code'
    assert result['data']['dashboard_auto'] is True


def test_guided_account_skip_stores_no_password(flow_module):
    result=asyncio.run(_flow(flow_module).async_step_setup_account({'cloud_enabled':False,'password':'must-not-persist'}))
    assert result['type']=='entry'
    assert 'password' not in result['data']


def test_guided_mqtt_failure_keeps_code_for_explicit_offline_save(flow_module, monkeypatch):
    module = sys.modules[flow_module.__package__ + '.setup_flow']
    def probe(*args):
        raise module.MqttSetupError('mqtt_auth_failed')
    monkeypatch.setattr(module, 'probe_mqtt', probe)
    flow = flow_module.Ultimate3DStudioOptionsFlow()
    flow.config_entry = SimpleNamespace(data={},options={})
    async def execute(fn,*args):return fn(*args)
    flow.hass = SimpleNamespace(async_add_executor_job=execute)
    flow._guided_candidates = {}
    first = asyncio.run(flow.async_step_setup_printer({'lan_enabled':True,'host':'192.0.2.1',
        'serial':'DEMO-SERIAL','access_code':'demo-only-code','verify_mqtt':True}))
    assert first['errors'] == {'base':'mqtt_auth_failed'}
    assert 'access_code' not in flow._guided_options
    assert 'demo-only-code' not in repr(first)
    second = asyncio.run(flow.async_step_setup_printer({'lan_enabled':True,'host':'192.0.2.1',
        'serial':'DEMO-SERIAL','verify_mqtt':False}))
    assert second['type'] == 'entry'
    assert second['data']['access_code'] == 'demo-only-code'


def test_initial_guided_setup_uses_private_seed_and_finishes_all_steps(flow_module,tmp_path,monkeypatch):
    import json,uuid
    secret='seed-only-'+ 'x'*48
    seed=tmp_path/'.taracraft-studio-setup.json'
    seed.write_text(json.dumps({'schema':1,'session':str(uuid.uuid4()),'slicer_base_url':'https://slicer.example.org','slicer_api_secret':secret}))
    seed.chmod(0o600)
    import os
    if os.name == 'nt':
        module=sys.modules[flow_module.__package__+'.setup_flow']
        monkeypatch.setattr(module,'read_setup_seed',lambda _: {'slicer_enabled':True,'slicer_base_url':'https://slicer.example.org','slicer_api_secret':secret})
    flow=flow_module.Ultimate3DStudioConfigFlow()
    flow.async_show_form=lambda **kw:{'type':'form',**kw}
    flow.async_create_entry=lambda **kw:{'type':'entry',**kw}
    async def noop(*args):return None
    flow.async_set_unique_id=noop;flow._abort_if_unique_id_configured=lambda:None
    async def execute(fn,*args):return fn(*args)
    flow.hass=SimpleNamespace(async_add_executor_job=execute,config=SimpleNamespace(config_dir=str(tmp_path)))
    flow._guided_candidates={}
    a=asyncio.run(flow.async_step_user({'instance_name':'Demo','guided_setup':True}))
    assert a['step_id']=='setup_printer' and secret not in repr(a)
    b=asyncio.run(flow.async_step_setup_printer({'lan_enabled':False}))
    assert b['step_id']=='setup_slicer' and secret not in repr(b)
    c=asyncio.run(flow.async_step_setup_slicer({'slicer_enabled':True,'verify_connection':False}))
    assert c['step_id']=='setup_account'
    d=asyncio.run(flow.async_step_setup_account({'cloud_enabled':False}))
    assert d['step_id']=='setup_dashboard'
    result=asyncio.run(flow.async_step_setup_dashboard({'dashboard_auto':True}))
    assert result['type']=='entry' and result['title']=='Demo'
    assert result['data']['slicer_api_secret']==secret and result['data']['dashboard_auto'] is True


def test_publicly_readable_seed_is_ignored(flow_module,tmp_path):
    import json,uuid
    seed=tmp_path/'.taracraft-studio-setup.json'
    seed.write_text(json.dumps({'schema':1,'session':str(uuid.uuid4()),'slicer_base_url':'https://slicer.example.org','slicer_api_secret':DEMO_SECRET}))
    seed.chmod(0o644)
    module=sys.modules[flow_module.__package__+'.setup_seed']
    assert module.read_setup_seed(tmp_path)=={}


def test_guided_mqtt_save_preserves_concurrent_cloud_token_rotation(flow_module,monkeypatch):
    module=sys.modules[flow_module.__package__+'.setup_flow']
    flow=_flow(flow_module,{'cloud_access_token':'old-cloud-token','slicer_api_secret':DEMO_SECRET})
    def probe(*args):flow.config_entry.options={**flow.config_entry.options,'cloud_access_token':'new-cloud-token'}
    monkeypatch.setattr(module,'probe_mqtt',probe)
    async def execute(fn,*args):return fn(*args)
    flow.hass=SimpleNamespace(async_add_executor_job=execute);flow._guided_candidates={}
    result=asyncio.run(flow.async_step_setup_printer({'lan_enabled':True,'host':'192.0.2.1',
        'serial':'DEMO','access_code':'synthetic-code','verify_mqtt':True}))
    assert result['data']['cloud_access_token']=='new-cloud-token'
    assert result['data']['slicer_api_secret']==DEMO_SECRET
