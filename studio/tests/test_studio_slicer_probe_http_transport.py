"""Real localhost HTTP transport tests for the read-only slicer connection probe.

Only a synthetic aiohttp listener on 127.0.0.1; no HA, printer or engine calls.
"""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

from aiohttp import ClientSession, web
import pytest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio"
TEST_SECRET = "integration-test-only-secret-" + "C" * 48
PACKAGE = "isolated_studio_transport_check"


@pytest.fixture
def probe(monkeypatch):
    package = ModuleType(PACKAGE)
    package.__path__ = [str(COMPONENT)]
    monkeypatch.setitem(sys.modules, PACKAGE, package)
    for name in ("slicer_connection_settings", "slicer_connection_probe"):
        fullname = PACKAGE + "." + name
        spec = importlib.util.spec_from_file_location(fullname, COMPONENT / (name + ".py"))
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, fullname, module)
        spec.loader.exec_module(module)
    return sys.modules[PACKAGE + ".slicer_connection_probe"]


async def _listen_and_probe(probe, handler, secret=TEST_SECRET):
    app = web.Application()
    app.router.add_get("/info.json", handler)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    try:
        server = web.TCPSite(runner, host="127.0.0.1", port=0)
        await server.start()
        assert server._server is not None and server._server.sockets
        port = server._server.sockets[0].getsockname()[1]
        async with ClientSession(trust_env=False) as session:
            return await probe.async_probe_slicer_connection(
                session, f"http://127.0.0.1:{port}", secret,
            )
    finally:
        await runner.cleanup()


def test_authenticated_connection_probe_over_real_localhost_http(probe):
    requests = []

    async def handler(request):
        requests.append((request.method, request.path, request.headers.get("Authorization", "")))
        if request.headers.get("Authorization") != "Bearer " + TEST_SECRET:
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response({
            "version": "synthetic-release",
            "api_version": 2,
            "capabilities": {"job_cancellation": True},
        })

    result = asyncio.run(_listen_and_probe(probe, handler))
    assert result == {
        "status": "ready",
        "server_version": "synthetic-release",
        "api_protocol": 2,
    }
    assert len(requests) == 1
    assert requests[0] == ("GET", "/info.json", "Bearer " + TEST_SECRET)


def test_connection_probe_bad_secret_returns_stable_auth_error(probe):
    requests = []

    async def handler(request):
        requests.append(request.path)
        if request.headers.get("Authorization") != "Bearer " + TEST_SECRET:
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response({"version": "synthetic-release", "api_version": 2})

    with pytest.raises(probe.SlicerConnectionProbeError, match="^slicer_auth_required$"):
        asyncio.run(_listen_and_probe(probe, handler, "other-test-secret-" + "D" * 48))
    assert requests == ["/info.json"]


def test_slicer_redirect_never_forwards_bearer_header(probe):
    requests = []

    async def handler(request):
        requests.append(request.path)
        raise web.HTTPFound(location="https://other-host.example.invalid/read-secret")

    with pytest.raises(probe.SlicerConnectionProbeError, match="^slicer_redirect_refused$"):
        asyncio.run(_listen_and_probe(probe, handler))
    assert requests == ["/info.json"]


def test_large_untrusted_slicer_response_is_rejected(probe):
    async def handler(_request):
        return web.Response(body=b"A" * 18_000, content_type="application/json")

    with pytest.raises(probe.SlicerConnectionProbeError, match="^slicer_incompatible$"):
        asyncio.run(_listen_and_probe(probe, handler))
