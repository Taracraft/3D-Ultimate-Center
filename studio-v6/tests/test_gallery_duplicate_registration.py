"""Check the real integration setup call, without starting Home Assistant."""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


def test_integration_setup_invokes_duplicate_registration_once():
    path = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6/__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
               and node.module == "gallery_duplicate_views"]
    assert len(imports) == 1
    assert [(alias.name, alias.asname) for alias in imports[0].names] == [("async_register_gallery_duplicate_views", None)]
    setup = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_setup")
    calls = {node.func.id for node in ast.walk(setup) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    scope = {name: Mock() for name in calls}
    audit = SimpleNamespace(async_append=AsyncMock())
    scope.update(DOMAIN="test_studio", DATA_RUNTIMES="runtimes", HomeAssistant=object,
                 ConfigType=dict, async_start_audit_runtime=AsyncMock(), get_audit_log=lambda _: audit)
    unit = ast.Module(body=[setup], type_ignores=[])
    exec(compile(ast.fix_missing_locations(unit), str(path), "exec"), scope)
    hass = SimpleNamespace(data={})
    assert asyncio.run(scope["async_setup"](hass, {})) is True
    scope["async_register_gallery_duplicate_views"].assert_called_once_with(hass)
    scope["async_register_gallery_management_views"].assert_called_once_with(hass)
    scope["async_register_slicer_queue_views"].assert_called_once_with(hass)
    audit.async_append.assert_awaited_once()
