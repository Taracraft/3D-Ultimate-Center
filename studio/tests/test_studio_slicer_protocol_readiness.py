"""Actual provider readiness contract with synthetic HTTP; no HA or network."""
from __future__ import annotations

import ast
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"
SYNTHETIC_SECRET = "test-only-provider-secret-" + "E" * 40


class Response:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def json(self, **_kwargs):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _provider(payload, *, http_status=200, transport_error=None):
    spec = importlib.util.spec_from_file_location(
        "provider_native_contract", COMPONENT / "slicer_native_contract.py",
    )
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    namespace = {name: value for name, value in vars(contract).items() if not name.startswith("__")}
    namespace.update({
        "BACKEND_SERVER": "server",
        "normalize_backend": lambda _backend: None,
        "ClientTimeout": lambda **kwargs: kwargs,
        "ClientError": ConnectionError,
    })
    tree = ast.parse((COMPONENT / "slicer_backend_router.py").read_text(encoding="utf-8-sig"))
    router = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "StudioSlicerBackendRouter")
    method = next(node for node in router.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_provider")
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        method,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "actual-provider", "exec"), namespace)
    calls = []

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        if transport_error is not None:
            raise transport_error(contract)
        return Response(http_status, payload)

    router = SimpleNamespace(session=SimpleNamespace(get=get), server_endpoint="https://slicer.example.invalid")
    result = asyncio.run(namespace["async_provider"](router))
    return result, calls


def _info(**overrides):
    return {
        "version": "0.1.0-alpha5",
        "api_version": 2,
        "status": "ready",
        "capabilities": {"job_cancellation": True, "cancellation_contract": 1},
        **overrides,
    }


@pytest.mark.parametrize("protocol", [None, 1, 3, 999, "2", True, 2.0])
def test_unknown_or_malformed_protocol_is_incompatible(protocol):
    result, calls = _provider(_info(api_version=protocol))
    assert result["mode"] == "offline"
    assert result["server"]["status"] == "incompatible"
    assert result["server"]["configured"] is True
    assert result["server"]["reachable"] is True
    assert result["capabilities"]["gcode_generation"] is False
    assert result["capabilities"]["job_cancellation"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [None, [], "ready", 7])
def test_non_object_info_is_classified_without_unhandled_exception(payload):
    result, calls = _provider(payload)
    assert result["mode"] == "offline"
    assert result["server"]["status"] == "incompatible"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "override",
    [
        {"version": None},
        {"version": ""},
        {"version": "x" * 61},
        {"version": "version\nsecret"},
        {"capabilities": None},
        {"capabilities": []},
        {"capabilities": "ready"},
        {"status": None},
        {"status": {"value": "ready"}},
        {"status": "unexpected"},
    ],
)
def test_malformed_info_envelope_is_incompatible(override):
    result, calls = _provider(_info(**override))
    assert result["server"]["status"] == "incompatible"
    assert result["mode"] == "offline"
    assert len(calls) == 1


@pytest.mark.parametrize("cancellation", [None, 0, 2, "1", True, 1.0])
def test_unsupported_cancellation_contract_disables_only_that_capability(cancellation):
    result, calls = _provider(_info(capabilities={
        "job_cancellation": True, "cancellation_contract": cancellation,
    }))
    assert result["mode"] == "native_gcode"
    assert result["capabilities"]["gcode_generation"] is True
    assert result["capabilities"]["job_cancellation"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("status", ["starting", "degraded"])
def test_compatible_but_not_ready_stays_reachable_and_keeps_offline_features(status):
    result, calls = _provider(_info(status=status))
    assert result["mode"] == "offline"
    assert result["server"]["status"] == status
    assert result["server"]["reachable"] is True
    assert result["capabilities"]["gcode_generation"] is False
    for name in ("geometry_preview", "layer_preview", "plan_persistence"):
        assert result["capabilities"][name] is True
    assert len(calls) == 1


def test_valid_native_protocol_and_cancellation_are_ready_without_mutations():
    result, calls = _provider(_info())
    assert result["mode"] == "native_gcode"
    assert result["capabilities"]["job_cancellation"] is True
    assert len(calls) == 1
    assert calls[0][0][0].endswith("/info")


def test_upstream_fields_cannot_override_local_connection_classification():
    result, _ = _provider(_info(configured=False, reachable=False))
    assert result["server"]["configured"] is True
    assert result["server"]["reachable"] is True


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failures_are_reachable_and_not_incompatible_or_unreachable(status):
    result, calls = _provider({"error": SYNTHETIC_SECRET}, http_status=status)
    assert result["server"]["status"] == "auth_failed"
    assert result["server"]["configured"] is True
    assert result["server"]["reachable"] is True
    assert result["mode"] == "offline"
    assert SYNTHETIC_SECRET not in str(result)
    assert len(calls) == 1


@pytest.mark.parametrize("status", [404, 405, 410, 501])
def test_missing_info_endpoint_is_incompatible(status):
    result, calls = _provider({"error": SYNTHETIC_SECRET}, http_status=status)
    assert result["server"]["status"] == "incompatible"
    assert result["server"]["reachable"] is True
    assert SYNTHETIC_SECRET not in str(result)
    assert len(calls) == 1


def test_disabled_or_unconfigured_transport_keeps_offline_features():
    result, calls = _provider(None, transport_error=lambda c: c.SlicerServerConfigurationError("disabled"))
    assert result["server"]["status"] == "unconfigured"
    assert result["server"]["configured"] is False
    assert result["mode"] == "offline"
    assert result["capabilities"]["geometry_preview"] is True
    assert len(calls) == 1


def test_timeout_is_unreachable_without_retry():
    result, calls = _provider(None, transport_error=lambda _c: TimeoutError("synthetic timeout"))
    assert result["server"]["status"] == "unreachable"
    assert result["server"]["reachable"] is False
    assert result["mode"] == "offline"
    assert len(calls) == 1
