"""Backend-only slicer transport tests; no HA installation, network or printer actions."""
from __future__ import annotations

import asyncio
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
TEST_SECRET = "test-only-secret-" + "B" * 48
TEST_BASE_URL = "https://slicer.example.org:8443"


class FakeResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.status = 200

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = FakeResponse()
        response.status = self.status
        return response


def _load(monkeypatch):
    namespace = "studio_native_slicer_transport_test"
    pkg = types.ModuleType(namespace)
    pkg.__path__ = [str(COMPONENT)]
    monkeypatch.setitem(sys.modules, namespace, pkg)

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    aiohttp = types.ModuleType("homeassistant.helpers.aiohttp_client")
    session = FakeSession()
    aiohttp.async_get_clientsession = lambda _hass: session
    for name, module in (
        ("homeassistant", homeassistant),
        ("homeassistant.core", core),
        ("homeassistant.helpers", helpers),
        ("homeassistant.helpers.aiohttp_client", aiohttp),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    constants = types.ModuleType(namespace + ".const")
    for key, value in {
        "DOMAIN": "ultimate_3d_studio",
        "CONF_SLICER_ENABLED": "slicer_enabled",
        "CONF_SLICER_BASE_URL": "slicer_base_url",
        "CONF_SLICER_API_SECRET": "slicer_api_secret",
    }.items():
        setattr(constants, key, value)
    monkeypatch.setitem(sys.modules, namespace + ".const", constants)

    def load(suffix: str):
        full_name = namespace + "." + suffix
        spec = importlib.util.spec_from_file_location(full_name, COMPONENT / (suffix + ".py"))
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, full_name, module)
        spec.loader.exec_module(module)
        return module

    load("slicer_connection_settings")
    contracts = load("slicer_native_contract")
    client = load("slicer_http_client")
    return client, contracts, session


def _hass(options):
    entry = SimpleNamespace(data={}, options=options)
    return SimpleNamespace(config_entries=SimpleNamespace(
        async_entries=lambda domain: [entry] if domain == "ultimate_3d_studio" else [],
    ))


def _config(**overrides):
    return {
        "slicer_enabled": True,
        "slicer_base_url": TEST_BASE_URL,
        "slicer_api_secret": TEST_SECRET,
        **overrides,
    }


def test_authenticated_get_and_post_stay_on_configured_https_host(monkeypatch):
    module, _, session = _load(monkeypatch)
    client = module.AuthenticatedSlicerSession(_hass(_config()))

    async def exercise():
        async with client.get(TEST_BASE_URL + "/info.json") as response:
            assert response.status == 200
        async with client.post(
            TEST_BASE_URL + "/jobs",
            headers={"Content-Type": "application/json"},
            json={"test": True},
        ) as response:
            assert response.status == 200

    asyncio.run(exercise())
    assert len(session.calls) == 2
    for method, url, kwargs in session.calls:
        assert method in {"GET", "POST"}
        assert url.startswith(TEST_BASE_URL + "/")
        assert kwargs["headers"]["Authorization"] == "Bearer " + TEST_SECRET
        assert kwargs["allow_redirects"] is False
        assert kwargs["ssl"] is True
    assert session.calls[1][2]["headers"]["Content-Type"] == "application/json"


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://slicer.example.org.evil.invalid/info.json",
        "http://slicer.example.org:8443/info.json",
        "https://another.example.org/info.json",
        TEST_BASE_URL + "@evil.invalid/info.json",
    ],
)
def test_cross_host_requests_cannot_receive_the_secret(monkeypatch, bad_url):
    module, contracts, session = _load(monkeypatch)
    client = module.AuthenticatedSlicerSession(_hass(_config()))

    async def exercise():
        with pytest.raises(contracts.SlicerServerConfigurationError):
            async with client.get(bad_url):
                pass

    asyncio.run(exercise())
    assert session.calls == []


def test_authentication_and_tls_transport_overrides_are_rejected(monkeypatch):
    module, contracts, session = _load(monkeypatch)
    client = module.AuthenticatedSlicerSession(_hass(_config()))

    async def exercise():
        for kwargs in (
            {"headers": {"Authorization": "Bearer attacker"}},
            {"headers": {"X-API-Token": "attacker"}},
            {"allow_redirects": True},
            {"ssl": False},
        ):
            with pytest.raises(contracts.SlicerServerConfigurationError):
                async with client.get(TEST_BASE_URL + "/info.json", **kwargs):
                    pass

    asyncio.run(exercise())
    assert session.calls == []


def test_server_redirect_is_rejected_without_forwarding_credentials(monkeypatch):
    module, contracts, session = _load(monkeypatch)
    session.status = 302
    client = module.AuthenticatedSlicerSession(_hass(_config()))

    async def exercise():
        with pytest.raises(contracts.SlicerServerError, match="redirect"):
            async with client.get(TEST_BASE_URL + "/info.json"):
                pass

    asyncio.run(exercise())
    assert len(session.calls) == 1
    assert session.calls[0][2]["allow_redirects"] is False


def test_unconfigured_slicer_is_closed_and_secret_is_never_in_error(monkeypatch):
    module, contracts, session = _load(monkeypatch)
    for options in (
        {},
        _config(slicer_enabled=False),
        _config(slicer_api_secret="too-short"),
        _config(slicer_base_url="http://remote.example.org"),
    ):
        client = module.AuthenticatedSlicerSession(_hass(options))
        with pytest.raises(contracts.SlicerServerConfigurationError) as error:
            _ = client.endpoint
        assert TEST_SECRET not in str(error.value)
    assert session.calls == []

@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_request_without_timeout_has_finite_backend_default(monkeypatch, method):
    module, _, session = _load(monkeypatch)
    client = module.AuthenticatedSlicerSession(_hass(_config()))

    async def exercise():
        async with getattr(client, method)(TEST_BASE_URL + "/info.json"):
            pass

    asyncio.run(exercise())
    timeout = session.calls[0][2]["timeout"]
    assert timeout.total == 30
    assert timeout.connect == 10
    assert timeout.sock_read == 30


@pytest.mark.parametrize("seconds", [10, 15, 30, 45, 300])
def test_existing_explicit_operation_timeout_is_preserved(monkeypatch, seconds):
    from aiohttp import ClientTimeout

    module, _, session = _load(monkeypatch)
    client = module.AuthenticatedSlicerSession(_hass(_config()))
    timeout = ClientTimeout(total=seconds, connect=4, sock_read=7)

    async def exercise():
        async with client.get(TEST_BASE_URL + "/info.json", timeout=timeout):
            pass

    asyncio.run(exercise())
    assert session.calls[0][2]["timeout"] is timeout


@pytest.mark.parametrize("invalid", [None, 0, -1, float("inf"), float("nan")])
def test_unbounded_or_invalid_timeout_rejected_before_request(monkeypatch, invalid):
    from aiohttp import ClientTimeout

    module, contracts, session = _load(monkeypatch)
    client = module.AuthenticatedSlicerSession(_hass(_config()))

    async def exercise():
        for timeout in (invalid, ClientTimeout(total=invalid)):
            with pytest.raises(contracts.SlicerServerConfigurationError, match="Zeitlimit") as error:
                async with client.get(TEST_BASE_URL + "/info.json", timeout=timeout):
                    pass
            assert TEST_SECRET not in str(error.value)

    asyncio.run(exercise())
    assert session.calls == []


def test_numeric_timeout_is_supported_and_bounded(monkeypatch):
    module, _, session = _load(monkeypatch)
    client = module.AuthenticatedSlicerSession(_hass(_config()))

    async def exercise():
        async with client.get(TEST_BASE_URL + "/info.json", timeout=12.5):
            pass

    asyncio.run(exercise())
    assert session.calls[0][2]["timeout"].total == 12.5


def test_timeout_exception_propagates_without_retry(monkeypatch):
    module, _, session = _load(monkeypatch)
    client = module.AuthenticatedSlicerSession(_hass(_config()))
    attempts = []

    def unavailable(*args, **kwargs):
        attempts.append((args, kwargs))
        raise TimeoutError("synthetic request timeout")

    session.request = unavailable

    async def exercise():
        with pytest.raises(TimeoutError):
            async with client.post(TEST_BASE_URL + "/jobs", json={"test": True}):
                pass

    asyncio.run(exercise())
    assert len(attempts) == 1

class FakeContent:
    def __init__(self, body, chunk_size=7):
        self.remaining = body
        self.chunk_size = chunk_size
        self.bytes_read = 0
        self.reads = 0

    async def read(self, size=-1):
        self.reads += 1
        amount = len(self.remaining) if size < 0 else min(size, self.chunk_size)
        chunk, self.remaining = self.remaining[:amount], self.remaining[amount:]
        self.bytes_read += len(chunk)
        return chunk


class BodyResponse(FakeResponse):
    def __init__(self, body, content_length=None):
        self.content = FakeContent(body)
        self.content_length = content_length
        self.closed = False
        self._body = None

    def close(self):
        self.closed = True

    async def read(self):
        if self._body is None:
            self._body = await self.content.read()
        return self._body

    async def json(self, **kwargs):
        import json
        return json.loads(await self.read())

    async def text(self):
        return (await self.read()).decode("utf-8")


def _body_client(monkeypatch, body, content_length=None):
    module, contracts, session = _load(monkeypatch)
    response = BodyResponse(body, content_length)

    def request(method, url, **kwargs):
        session.calls.append((method, url, kwargs))
        return response

    session.request = request
    client = module.AuthenticatedSlicerSession(_hass(_config()))
    return module, contracts, session, client, response


@pytest.mark.parametrize(
    "reader,constant,body",
    [
        ("json", "MAX_JSON_RESPONSE_BYTES", b'{"value":"abcdefghijk"}'),
        ("text", "MAX_TEXT_RESPONSE_BYTES", b"abcdefghijklmnopqrstuv"),
        ("read", "MAX_ARTIFACT_RESPONSE_BYTES", b"abcdefghijklmnopqrstuv"),
    ],
)
@pytest.mark.parametrize("declared", [None, 1, 100])
def test_response_limits_reject_before_unbounded_read(
    monkeypatch, reader, constant, body, declared,
):
    module, contracts, session, client, response = _body_client(monkeypatch, body, declared)
    monkeypatch.setattr(module, constant, 16, raising=False)

    async def exercise():
        with pytest.raises(contracts.SlicerServerError) as error:
            async with client.post(TEST_BASE_URL + "/jobs", json={"test": True}) as reply:
                await getattr(reply, reader)()
        assert TEST_SECRET not in str(error.value)

    asyncio.run(exercise())
    assert len(session.calls) == 1
    assert response.content.bytes_read <= 17
    if declared == 100:
        assert response.content.reads == 0
    assert response.closed is True


@pytest.mark.parametrize(
    "reader,constant,body,expected",
    [
        ("json", "MAX_JSON_RESPONSE_BYTES", b'{"ok":true}', {"ok": True}),
        ("text", "MAX_TEXT_RESPONSE_BYTES", b"hello world", "hello world"),
        ("read", "MAX_ARTIFACT_RESPONSE_BYTES", b"binary\x00data", b"binary\x00data"),
    ],
)
def test_exact_limit_and_short_chunks_preserve_valid_response(
    monkeypatch, reader, constant, body, expected,
):
    module, _, session, client, response = _body_client(monkeypatch, body, len(body))
    monkeypatch.setattr(module, constant, len(body), raising=False)

    async def exercise():
        async with client.get(TEST_BASE_URL + "/info.json") as reply:
            assert await getattr(reply, reader)() == expected
            reads = response.content.reads
            assert await getattr(reply, reader)() == expected
            assert response.content.reads == reads

    asyncio.run(exercise())
    assert len(session.calls) == 1


def test_cached_binary_body_cannot_bypass_smaller_json_limit(monkeypatch):
    body = b'{"value":"abcdefghijk"}'
    module, contracts, session, client, response = _body_client(monkeypatch, body)
    monkeypatch.setattr(module, "MAX_ARTIFACT_RESPONSE_BYTES", len(body), raising=False)
    monkeypatch.setattr(module, "MAX_JSON_RESPONSE_BYTES", 16, raising=False)

    async def exercise():
        async with client.get(TEST_BASE_URL + "/info.json") as reply:
            assert await reply.read() == body
            with pytest.raises(contracts.SlicerServerError):
                await reply.json(content_type=None)

    asyncio.run(exercise())
    assert len(session.calls) == 1
    assert response.closed is True


@pytest.mark.parametrize("body", [TEST_SECRET.encode(), b"\xff", b"[" * 20000], ids=["malformed", "non_utf8", "nested"])
def test_invalid_json_has_stable_error_without_response_or_secret(monkeypatch, body):
    _, contracts, session, client, _ = _body_client(monkeypatch, body)

    async def exercise():
        with pytest.raises(contracts.SlicerServerError) as error:
            async with client.get(TEST_BASE_URL + "/info.json") as reply:
                await reply.json(content_type=None)
        assert TEST_SECRET not in str(error.value)
        assert str(error.value) == "Slicer-Server lieferte keine gueltige JSON-Antwort"

    asyncio.run(exercise())
    assert len(session.calls) == 1

def test_oversize_response_stays_rejected_on_subsequent_reads(monkeypatch):
    module, contracts, session, client, response = _body_client(monkeypatch, b"a" * 30)
    monkeypatch.setattr(module, "MAX_TEXT_RESPONSE_BYTES", 16)

    async def exercise():
        async with client.get(TEST_BASE_URL + "/info.json") as reply:
            with pytest.raises(contracts.SlicerServerError):
                await reply.text()
            reads = response.content.reads
            with pytest.raises(contracts.SlicerServerError):
                await reply.read()
            assert response.content.reads == reads

    asyncio.run(exercise())
    assert len(session.calls) == 1


def test_aiohttp_decompressed_stream_is_bounded_by_decoded_bytes(monkeypatch):
    import zlib
    from unittest.mock import Mock
    from aiohttp import StreamReader

    body = b"a" * 512
    compressed = zlib.compress(body)
    module, contracts, session, client, response = _body_client(monkeypatch, body)
    monkeypatch.setattr(module, "MAX_ARTIFACT_RESPONSE_BYTES", 128)

    async def exercise():
        reader = StreamReader(Mock(), 2**16, loop=asyncio.get_running_loop())
        # aiohttp's HTTP parser supplies decompressed bytes to StreamReader.
        reader.feed_data(zlib.decompress(compressed))
        reader.feed_eof()
        response.content = reader
        response.content_length = len(compressed)
        with pytest.raises(contracts.SlicerServerError):
            async with client.get(TEST_BASE_URL + "/download") as reply:
                await reply.read()

    asyncio.run(exercise())
    assert len(compressed) < 128 < len(body)
    assert response.closed is True
    assert len(session.calls) == 1
