"""Connection-scoped caches using actual client/router/view bodies and fake HTTP."""
from __future__ import annotations
import ast
import asyncio
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
import re
from types import SimpleNamespace
import pytest
from tests.test_studio_slicer_http_client import _load, _hass, _config

COMPONENT = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio"


class Response:
    status = 200
    def __init__(self, payload, raw=b"artifact"):
        self.payload, self.raw = payload, raw
    async def __aenter__(self): return self
    async def __aexit__(self, *_args): return False
    async def json(self, **_kwargs): return self.payload
    async def read(self): return self.raw


def execute(filename, names, namespace):
    tree = ast.parse((COMPONENT / filename).read_text(encoding="utf-8-sig"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), filename, "exec"), namespace)


def setup(monkeypatch):
    client, contracts, _ = _load(monkeypatch)
    options = _config()
    hass = _hass(options)
    hass.data = {}
    async def executor(fn, *args): return fn(*args)
    hass.async_add_executor_job = executor
    calls = []
    async def noop(*args): pass
    ns = {
        "OrderedDict": OrderedDict, "re": re, "deepcopy": deepcopy,
        "AuthenticatedSlicerSession": client.AuthenticatedSlicerSession,
        "ClientTimeout": lambda **kw: kw, "ClientError": ConnectionError,
        "SERVER_PREFIX": "server__", "BACKEND_SERVER": "server",
        "DATA_TOOLPATH_CACHE": "ultimate_3d_studio_toolpath_cache",
        "SlicerServerError": contracts.SlicerServerError,
        "SlicerServerConfigurationError": contracts.SlicerServerConfigurationError,
        "_COMPLETED_ARTIFACT_CACHE": OrderedDict(), "_MAX_COMPLETED_ARTIFACT_CACHE": 1,
        "_COMPLETED_METADATA_CACHE": OrderedDict(), "_MAX_COMPLETED_METADATA_CACHE": 100,
        "_server_job": lambda payload, metadata=None: {"payload": payload, "metadata": metadata},
        "_prepare_server_artifact": lambda raw_id, payload, raw: (raw, raw_id+".3mf", raw.decode(), {"proof": raw.decode()}),
    }
    execute("slicer_backend_router.py", {"StudioSlicerBackendRouter", "native_job_id", "SlicerCancellationError", "_cached_artifact", "_cached_metadata", "_store_artifact"}, ns)
    router = ns["StudioSlicerBackendRouter"](hass)
    def get(url, **kw):
        # Exercise the real current connection validation, with no actual network.
        base = router.session.endpoint
        assert url.startswith(base + "/")
        calls.append(url)
        if url.endswith("/download"):
            return Response({}, base.encode())
        payload = {"job_id": "same", "status": "completed"}
        return Response({"jobs": [payload]} if url.endswith("/jobs") else payload)
    router.session.get = get
    return ns, client, contracts, hass, options, router, calls


@pytest.mark.parametrize("change", ["server", "credential"])
def test_metadata_and_artifact_never_cross_connections(monkeypatch, change):
    ns, _, _, _, options, router, calls = setup(monkeypatch)
    async def run():
        first = await router.async_artifact("server__same")
        assert (await router.async_get_job("server__same"))["metadata"] is not None
        if change == "server": options["slicer_base_url"] = "https://other.example.org"
        else: options["slicer_api_secret"] = "test-rotated-" + "R"*48
        assert (await router.async_get_job("server__same"))["metadata"] is None
        assert (await router.async_list_jobs())[0]["metadata"] is None
        await router.async_artifact("server__same")
        assert sum(url.endswith("/download") for url in calls) == 2
    asyncio.run(run())


def test_same_connection_reuses_artifact_without_reanalysis(monkeypatch):
    _, _, _, _, _, router, calls = setup(monkeypatch)
    async def run():
        await router.async_artifact("server__same")
        await router.async_artifact("server__same")
    asyncio.run(run())
    assert sum(url.endswith("/download") for url in calls) == 1


def test_scope_is_shared_by_routers_but_not_by_ha_instances(monkeypatch):
    _, client, _, hass, _, router, _ = setup(monkeypatch)
    assert router.cache_scope == client.AuthenticatedSlicerSession(hass).cache_scope
    assert router.cache_scope != client.AuthenticatedSlicerSession(_hass(_config())).cache_scope
    assert isinstance(router.cache_scope, bytes)
    assert len(router.cache_scope) == 32
    assert _config()["slicer_api_secret"].encode() not in router.cache_scope


@pytest.mark.parametrize("override", [
    {"slicer_enabled": False}, {"slicer_api_secret": "short"}, {"slicer_base_url": "http://remote.example.org"},
])
def test_completed_cache_cannot_bypass_disabled_or_invalid_connection(monkeypatch, override):
    _, _, contracts, _, options, router, _ = setup(monkeypatch)
    async def run():
        await router.async_artifact("server__same")
        options.update(override)
        with pytest.raises(contracts.SlicerServerConfigurationError):
            await router._server_completed_artifact("same", {"status": "completed"})
    asyncio.run(run())


def test_connection_change_during_analysis_is_not_cached(monkeypatch):
    ns, _, contracts, hass, options, router, _ = setup(monkeypatch)
    async def executor(fn, *args):
        options["slicer_base_url"] = "https://changed.example.org"
        return fn(*args)
    hass.async_add_executor_job = executor
    with pytest.raises(contracts.SlicerServerConfigurationError):
        asyncio.run(router.async_artifact("server__same"))
    assert ns["_COMPLETED_ARTIFACT_CACHE"] == {}
    assert ns["_COMPLETED_METADATA_CACHE"] == {}


def toolpath_view(monkeypatch):
    ns, _, contracts, hass, options, router, calls = setup(monkeypatch)
    ns.update({
        "HomeAssistantView": object, "API_PREFIX": "/api/studio",
        "_CACHE_KEY": "test_toolpaths", "_CACHE_LIMIT": 3,
        "StudioSlicerBackendRouter": lambda _hass: router,
        "web": SimpleNamespace(json_response=lambda body, status=200, headers=None: SimpleNamespace(body=body, status=status, headers=headers or {})),
    })
    execute("slicer_toolpath_views.py", {"_cache", "_response_from_cached", "SlicerJobToolpathView"}, ns)
    ns["_complete_toolpath"] = lambda data: {"source": data.decode(), "chunk": {"layers": [{"segments": []}]}}
    view = ns["SlicerJobToolpathView"]()
    request = SimpleNamespace(app={"hass": hass}, query={})
    return ns, contracts, hass, options, router, calls, view, request


@pytest.mark.parametrize("change", ["server", "credential"])
def test_toolpath_does_not_reuse_other_connections(monkeypatch, change):
    _, _, _, options, _, calls, view, request = toolpath_view(monkeypatch)
    async def run():
        first = await view.get(request, "server__same")
        assert first.status == 200
        same = await view.get(request, "server__same")
        assert same.headers["X-U3D-Toolpath-Cache"] == "hit"
        if change == "server": options["slicer_base_url"] = "https://other.example.org"
        else: options["slicer_api_secret"] = "rotated-" + "T"*48
        second = await view.get(request, "server__same")
        assert second.status == 200
        assert second.headers["X-U3D-Toolpath-Cache"] == "miss"
        assert second.headers["Cache-Control"] == "no-store"
        assert sum(url.endswith("/download") for url in calls) == 2
    asyncio.run(run())


@pytest.mark.parametrize("override", [
    {"slicer_enabled": False}, {"slicer_api_secret": "short"}, {"slicer_base_url": "bad"},
])
def test_toolpath_cache_hit_requires_valid_enabled_connection(monkeypatch, override):
    _, _, _, options, _, calls, view, request = toolpath_view(monkeypatch)
    async def run():
        assert (await view.get(request, "server__same")).status == 200
        count = len(calls)
        options.update(override)
        reply = await view.get(request, "server__same")
        assert reply.status == 502
        assert len(calls) == count
    asyncio.run(run())


def test_toolpath_change_during_parse_does_not_store_old_data(monkeypatch):
    ns, _, hass, options, _, _, view, request = toolpath_view(monkeypatch)
    original = hass.async_add_executor_job
    async def executor(fn, *args):
        result = await original(fn, *args)
        if fn is ns["_complete_toolpath"]:
            options["slicer_api_secret"] = "rotated-" + "Z"*48
        return result
    hass.async_add_executor_job = executor
    assert asyncio.run(view.get(request, "server__same")).status == 502
    assert ns["_cache"](hass) == {}

@pytest.mark.parametrize("action", ["delete", "cancel"])
@pytest.mark.parametrize("confirmed", [True, False])
def test_mutation_invalidates_only_confirmed_jobs_in_current_scope(monkeypatch, action, confirmed):
    ns, _, _, hass, options, router, _ = setup(monkeypatch)
    cache_key = "ultimate_3d_studio_toolpath_cache"
    ns["DATA_TOOLPATH_CACHE"] = cache_key
    scope = router.cache_scope
    target = (scope, "same")
    peer = (scope, "other")
    other_scope = (b"other-connection", "same")
    for name in ["_COMPLETED_ARTIFACT_CACHE", "_COMPLETED_METADATA_CACHE"]:
        ns[name].update({target: object(), peer: object(), other_scope: object()})
    toolpaths = OrderedDict({(scope, "server__same"): object(),
                             (scope, "server__other"): object(),
                             (b"other-connection", "server__same"): object()})
    hass.data[cache_key] = toolpaths
    before = {name: dict(ns[name]) for name in ["_COMPLETED_ARTIFACT_CACHE", "_COMPLETED_METADATA_CACHE"]}
    before_tool = dict(toolpaths)
    payload = ({"deleted": confirmed} if action == "delete" else
               {"job_id": "same", "status": "cancelled", "cancel_requested": confirmed})
    calls = []
    def mutate(*args, **kwargs):
        calls.append(args[0])
        return Response(payload)
    setattr(router.session, action if action == "delete" else "post", mutate)
    async def run():
        method = router.async_delete_job if action == "delete" else router.async_cancel_job
        if confirmed:
            await method("server__same")
        else:
            with pytest.raises(ns["SlicerServerError"]):
                await method("server__same")
    asyncio.run(run())
    assert len(calls) == 1
    if confirmed:
        assert target not in ns["_COMPLETED_ARTIFACT_CACHE"]
        assert target not in ns["_COMPLETED_METADATA_CACHE"]
        assert (scope, "server__same") not in toolpaths
        assert peer in ns["_COMPLETED_ARTIFACT_CACHE"]
        assert peer in ns["_COMPLETED_METADATA_CACHE"]
        assert other_scope in ns["_COMPLETED_METADATA_CACHE"]
        assert (scope, "server__other") in toolpaths
        assert (b"other-connection", "server__same") in toolpaths
    else:
        for name, original in before.items():
            assert dict(ns[name]) == original
        assert dict(toolpaths) == before_tool

@pytest.mark.parametrize("action", ["delete", "cancel"])
def test_confirmed_mutation_without_toolpath_cache_does_not_create_one(monkeypatch, action):
    ns, _, _, hass, _, router, _ = setup(monkeypatch)
    ns["DATA_TOOLPATH_CACHE"] = "ultimate_3d_studio_toolpath_cache"
    payload = {"deleted": True, "job_id": "same", "status": "cancelled", "cancel_requested": True}
    setattr(router.session, action if action == "delete" else "post", lambda *args, **kw: Response(payload))
    method = router.async_delete_job if action == "delete" else router.async_cancel_job
    asyncio.run(method("server__same"))
    assert ns["DATA_TOOLPATH_CACHE"] not in hass.data
