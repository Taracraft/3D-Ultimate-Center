"""Connection-test contract: backend GET only, no jobs or printer actions."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest


COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio"
)
DEMO_URL = "https://slicer.example.invalid:8443"
DEMO_SECRET = "synthetic-secret-" + "Q" * 48


@pytest.fixture
def probe(monkeypatch):
    name = "standalone_slicer_probe_test"
    package = types.ModuleType(name)
    package.__path__ = [str(COMPONENT)]
    monkeypatch.setitem(sys.modules, name, package)
    for source in ("slicer_connection_settings", "slicer_connection_probe"):
        qualified = name + "." + source
        spec = importlib.util.spec_from_file_location(
            qualified, COMPONENT / (source + ".py")
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, qualified, module)
        spec.loader.exec_module(module)
    return sys.modules[name + ".slicer_connection_probe"]


class FakeContent:
    def __init__(self, body: bytes):
        self.body = body

    async def read(self, limit):
        return self.body[:limit]


class FakeResponse:
    def __init__(self, status=200, body: bytes | None = None):
        self.status = status
        self.content = FakeContent(
            body if body is not None else json.dumps({
                "version": "0.1.0-alpha5",
                "api_version": 2,
                "capabilities": {"job_cancellation": True},
            }).encode()
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response = response or FakeResponse()
        self.exc = exc
        self.calls = []

    def get(self, path, **kwargs):
        self.calls.append((path, kwargs))
        if self.exc:
            raise self.exc
        return self.response


def test_connection_probe_requires_secure_single_readonly_get_and_valid_secret(probe):
    session = FakeSession()
    result = asyncio.run(probe.async_probe_slicer_connection(
        session, DEMO_URL + "/", DEMO_SECRET,
    ))
    assert result == {
        "status": "ready", "server_version": "0.1.0-alpha5", "api_protocol": 2
    }
    assert len(session.calls) == 1
    endpoint, opts = session.calls[0]
    assert endpoint == DEMO_URL + "/info.json"
    assert opts["headers"]["Authorization"] == "Bearer " + DEMO_SECRET
    assert opts["headers"]["Accept"] == "application/json"
    assert opts["allow_redirects"] is False
    assert opts["ssl"] is True
    assert opts["timeout"].total <= 8


@pytest.mark.parametrize(("status", "error"), [
    (401, "slicer_auth_required"),
    (403, "slicer_auth_required"),
    (404, "slicer_incompatible"),
    (302, "slicer_redirect_refused"),
    (503, "slicer_unavailable"),
])
def test_status_errors_do_not_disclose_credentials(probe, status, error):
    session = FakeSession(response=FakeResponse(status=status))
    with pytest.raises(probe.SlicerConnectionProbeError) as exc:
        asyncio.run(probe.async_probe_slicer_connection(
            session, DEMO_URL, DEMO_SECRET,
        ))
    assert str(exc.value) == error
    assert DEMO_SECRET not in str(exc.value)
    assert DEMO_URL not in str(exc.value)


@pytest.mark.parametrize("body", [
    b"",
    b"<html>not a slicer</html>",
    b"[]",
    b'{"version":"synthetic","api_version":1,"capabilities":{}}',
    b'{"version":"synthetic","api_version":2}',
    b'{"version":"secret\\nvalue","api_version":2,"capabilities":{}}',
    b"X" * 16_390,
])
def test_malformed_or_incompatible_server_info_is_rejected(probe, body):
    session = FakeSession(response=FakeResponse(body=body))
    with pytest.raises(probe.SlicerConnectionProbeError, match="slicer_incompatible"):
        asyncio.run(probe.async_probe_slicer_connection(
            session, DEMO_URL, DEMO_SECRET,
        ))


def test_invalid_secret_or_url_fails_before_any_network_request(probe):
    session = FakeSession()
    for url, secret in (
        ("http://remote.example.invalid:8099", DEMO_SECRET),
        (DEMO_URL, "short"),
        ("https://user:secret@slicer.example.invalid", DEMO_SECRET),
    ):
        with pytest.raises(probe.SlicerConnectionProbeError):
            asyncio.run(probe.async_probe_slicer_connection(session, url, secret))
    assert session.calls == []


def test_timeout_is_a_stable_unavailable_status(probe):
    session = FakeSession(exc=TimeoutError("sensitive hostname hidden"))
    with pytest.raises(probe.SlicerConnectionProbeError) as exc:
        asyncio.run(probe.async_probe_slicer_connection(
            session, DEMO_URL, DEMO_SECRET,
        ))
    assert str(exc.value) == "slicer_unavailable"
    assert "sensitive" not in str(exc.value)
