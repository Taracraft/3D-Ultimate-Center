"""Offline Lovelace resource registration contract; no live HA writes."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = (
    ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio"
    / "lovelace_resources.py"
)
spec = importlib.util.spec_from_file_location("studio_lovelace_resources_contract", MODULE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DummyStorage:
    def __init__(self, entries=None):
        self.entries = list(entries or [])
        self.loaded = False
        self.creations = []

    async def async_get_info(self):
        self.loaded = True
        return {"resources": len(self.entries)}

    def async_items(self):
        assert self.loaded, "Lovelace resources must be loaded before inspection"
        return self.entries

    async def async_create_item(self, entry):
        assert self.loaded
        self.creations.append(dict(entry))
        item = {"url": entry["url"], "type": entry["res_type"]}
        self.entries.append(item)
        return item


@pytest.mark.asyncio
async def test_new_hacs_install_registers_exactly_one_module_in_storage_mode():
    store = DummyStorage()
    lovelace = SimpleNamespace(resource_mode="storage", resources=store)
    first = await module.async_ensure_studio_lovelace_resource(lovelace)
    second = await module.async_ensure_studio_lovelace_resource(lovelace)
    assert first == "registered"
    assert second == "already_registered"
    assert store.creations == [
        {"url": module.RESOURCE_URL, "res_type": "module"},
    ]
    assert all(item["type"] == "module" for item in store.entries)


@pytest.mark.asyncio
async def test_existing_resource_with_cache_parameter_is_not_duplicated():
    existing = {"url": module.RESOURCE_URL + "?build=test", "type": "module"}
    store = DummyStorage([existing])
    assert (
        await module.async_ensure_studio_lovelace_resource(
            SimpleNamespace(resource_mode="storage", resources=store)
        )
        == "already_registered"
    )
    assert store.entries == [existing]
    assert store.creations == []


@pytest.mark.asyncio
async def test_old_lovelace_url_preserved_without_creating_duplicate_card():
    existing = {"url": module.LEGACY_RESOURCE_URL + "?cache=old", "type": "module"}
    store = DummyStorage([existing])
    assert (
        await module.async_ensure_studio_lovelace_resource(
            SimpleNamespace(resource_mode="storage", resources=store)
        )
        == "legacy_resource_preserved"
    )
    assert store.entries == [existing]
    assert store.creations == []


@pytest.mark.asyncio
async def test_wrong_resource_type_is_not_silently_overwritten():
    store = DummyStorage([{"url": module.RESOURCE_URL, "type": "js"}])
    result = await module.async_ensure_studio_lovelace_resource(
        SimpleNamespace(resource_mode="storage", resources=store)
    )
    assert result == "type_conflict"
    assert store.creations == []


@pytest.mark.asyncio
async def test_yaml_mode_and_missing_lovelace_do_not_modify_any_resource():
    store = DummyStorage()
    yaml = SimpleNamespace(resource_mode="yaml", resources=store)
    assert await module.async_ensure_studio_lovelace_resource(None) == "lovelace_not_loaded"
    assert await module.async_ensure_studio_lovelace_resource(yaml) == "non_storage_mode"
    assert not store.loaded
    assert store.creations == []


def test_static_route_and_auto_registration_are_scoped_to_bundled_assets():
    source = (
        ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/__init__.py"
    ).read_text(encoding="utf-8")
    assert 'asset_root = Path(__file__).resolve().parent / "assets"' in source
    assert '"ui_assets_registered"' in source
    assert 'domain_data["lovelace_resource_status"] = await async_ensure_studio_lovelace_resource(' in source
    assert source.count(
        'domain_data["lovelace_resource_status"] = await async_ensure_studio_lovelace_resource('
    ) == 2
    assert 'in {"lovelace_not_loaded", "resources_unavailable"}' in source
    assert "StaticPathConfig(\"/ultimate-3d-studio/assets\"" in source


@pytest.mark.asyncio
async def test_lovelace_late_loading_can_complete_registration_on_retry():
    first = await module.async_ensure_studio_lovelace_resource(None)
    assert first == "lovelace_not_loaded"
    store = DummyStorage()
    result = await module.async_ensure_studio_lovelace_resource(
        SimpleNamespace(resource_mode="storage", resources=store)
    )
    assert result == "registered"
    assert store.entries == [{"url": module.RESOURCE_URL, "type": "module"}]
