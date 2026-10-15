"""Connected hardware identity regression; no network or printer operations."""
from __future__ import annotations

import ast
import asyncio
from functools import partial
import importlib.util
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio"
PACKAGE = "studio_identity_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = package
spec = importlib.util.spec_from_file_location(PACKAGE + ".printer_identity", COMPONENT / "printer_identity.py")
assert spec and spec.loader
identity = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = identity
spec.loader.exec_module(identity)
from studio_identity_test.printer_model_contract import hardware_limits

A1_SERIAL = "039000000000001"
H2S_SERIAL = "093000000000001"


@pytest.mark.parametrize("reported,serial,expected", [
    (None,A1_SERIAL,"A1"),("",A1_SERIAL,"A1"),(" A1 ",A1_SERIAL,"A1"),
    ("Bambu Lab A1",A1_SERIAL,"A1"),("N2S",A1_SERIAL,"A1"),
    (None,H2S_SERIAL,"H2S"),("H2S",H2S_SERIAL,"H2S"),("O1S",H2S_SERIAL,"H2S"),
    ("H2S",A1_SERIAL,None),("A1",H2S_SERIAL,None),
    ("A1 mini",A1_SERIAL,None),("AMS",A1_SERIAL,None),("unknown",A1_SERIAL,None),
    ("A1","030000000000001",None),("H2S","094000000000001",None),
    (None,"X1C000000000001",None),("A1",None,None),(None,"039",None),
    (None,"039/00000000001",None),(None,"039\n00000000001",None),
])
def test_identity_is_bound_to_connected_serial_and_matching_telemetry(reported, serial, expected):
    assert identity.resolve_connected_printer_model(reported,serial) == expected


def provider_contract():
    tree = ast.parse((COMPONENT / "provider_bambu_lan.py").read_text())
    provider = next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name == "BambuLanProvider")
    methods = [node for node in provider.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in {"resolved_model","async_upload_print_artifact"}]
    assert len(methods) == 2
    reduced = ast.ClassDef(name="ProviderProbe",bases=[],keywords=[],body=methods,decorator_list=[])
    namespace = {"partial":partial,"resolve_connected_printer_model":identity.resolve_connected_printer_model,"hardware_limits":hardware_limits}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0),reduced],type_ignores=[])),"provider-contract","exec"),namespace)
    return namespace


def test_upload_uses_same_verified_identity_as_snapshot_without_network():
    ns = provider_contract()
    captured = {}
    def capture_upload(**arguments):
        captured.update(arguments)
        return "dry-run-only"
    ns["upload_gcode_3mf"] = capture_upload
    class FakeHass:
        async def async_add_executor_job(self,operation):
            return operation()
    provider = ns["ProviderProbe"]()
    provider.hass = FakeHass()
    provider.serial = A1_SERIAL
    provider.telemetry = types.SimpleNamespace(model=None)
    provider.connected = True
    provider.host = "unused.invalid"
    provider.access_code = "unit-test-placeholder"
    provider.tls_insecure = False
    assert provider.resolved_model == "A1"
    result = asyncio.run(provider.async_upload_print_artifact(A1_SERIAL,"test.3mf",b"test"))
    assert result == "dry-run-only"
    assert captured["printer_model"] == "A1"
    assert captured["hardware_limits"]["max_nozzle_temperature_c"] == 300
    assert captured["hardware_limits"]["max_bed_temperature_c"] == 100
    assert captured["hardware_limits"]["width_mm"] == 256
    source = (COMPONENT / "provider_bambu_lan.py").read_text()
    assert "model=self.resolved_model," in source
    assert "hardware_limits(self.telemetry.model)" not in source


def test_conflicting_connected_identity_is_rejected_before_executor():
    ns = provider_contract()
    class NoExecutor:
        async def async_add_executor_job(self,*args):
            raise AssertionError("No upload executor may run")
    provider = ns["ProviderProbe"]()
    provider.hass = NoExecutor()
    provider.serial = A1_SERIAL
    provider.telemetry = types.SimpleNamespace(model="H2S")
    provider.connected = True
    with pytest.raises(RuntimeError,match="nicht eindeutig"):
        asyncio.run(provider.async_upload_print_artifact(A1_SERIAL,"test.3mf",b"test"))
