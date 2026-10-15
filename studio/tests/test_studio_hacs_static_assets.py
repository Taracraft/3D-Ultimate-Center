"""Isolated Home Assistant async-setup static-resource registration tests.

Runs only the real async_setup method body with mocked HA services.
No live HTTP port, dashboard changes, filesystem writes or registered HA UI.
"""
from __future__ import annotations
import asyncio
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/__init__.py"


class FakeAudit:
    async def async_append(self, **_kwargs):
        return None


class FakeHttp:
    def __init__(self):
        self.routes = []

    async def async_register_static_paths(self, routes):
        self.routes.extend(routes)


async def no_effect(*_args, **_kwargs):
    return None


async def fake_lovelace_registration(_lovelace_data):
    """Isolated setup has no Lovelace collection; registration is tested separately."""
    return "lovelace_not_loaded"


def _load_async_setup(component_path):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_setup"
    )
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        function,
    ], type_ignores=[])
    ast.fix_missing_locations(module)
    scope = {
        "__file__": str(component_path / "__init__.py"),
        "Path": Path,
        "DOMAIN": "ultimate_3d_studio",
        "DATA_RUNTIMES": "runtimes",
        "StaticPathConfig": lambda url_path, path, cache: SimpleNamespace(
            url_path=url_path, path=path, cache_headers=cache
        ),
        "install_profile_runtime_v2": lambda _hass: None,
        "async_start_audit_runtime": no_effect,
        "async_ensure_studio_lovelace_resource": fake_lovelace_registration,
        "get_audit_log": lambda _hass: FakeAudit(),
    }
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id.startswith("async_register_"):
                scope[node.func.id] = lambda _hass: None
    exec(compile(module, str(SOURCE), "exec"), scope)
    return scope["async_setup"]


def test_hacs_assets_auto_register_with_backend_static_route(tmp_path):
    package = tmp_path / "integration"
    assets = package / "assets"
    assets.mkdir(parents=True)
    for name in ("ultimate-3d-studio.js", "ultimate-3d-studio.css",
                 "ultimate-3d-studio-build.json"):
        (assets / name).write_text("synthetic static payload")
    hass = SimpleNamespace(data={}, http=FakeHttp())
    setup = _load_async_setup(package)
    assert asyncio.run(setup(hass, {})) is True
    assert len(hass.http.routes) == 1
    route = hass.http.routes[0]
    assert route.url_path == "/ultimate-3d-studio/assets"
    assert Path(route.path) == assets
    assert route.cache_headers is False
    assert hass.data["ultimate_3d_studio"]["lovelace_resource_status"] == "lovelace_not_loaded"
    assert asyncio.run(setup(hass, {})) is True
    assert len(hass.http.routes) == 1, "reload must not double-register assets"


def test_incomplete_hacs_assets_fail_before_registering_partial_bundle(tmp_path):
    package = tmp_path / "integration"
    assets = package / "assets"
    assets.mkdir(parents=True)
    (assets / "ultimate-3d-studio.js").write_text("synthetic incomplete asset")
    hass = SimpleNamespace(data={}, http=FakeHttp())
    setup = _load_async_setup(package)
    with pytest.raises(RuntimeError, match="incomplete"):
        asyncio.run(setup(hass, {}))
    assert not hass.http.routes


def test_legacy_live_without_hacs_asset_directory_still_initializes(tmp_path):
    package = tmp_path / "integration"
    package.mkdir()
    hass = SimpleNamespace(data={}, http=FakeHttp())
    setup = _load_async_setup(package)
    assert asyncio.run(setup(hass, {})) is True
    assert hass.http.routes == []
    assert "lovelace_resource_status" not in hass.data["ultimate_3d_studio"]
