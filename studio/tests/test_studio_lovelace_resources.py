"""Offline Lovelace resource registration contract; no live HA writes."""
from __future__ import annotations

import importlib.util
import hashlib
import json
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


@pytest.fixture(autouse=True)
def packaged_assets(tmp_path, monkeypatch):
    payload = b"export const studio = true;"
    (tmp_path / "ultimate-3d-studio.js").write_bytes(payload)
    (tmp_path / "ultimate-3d-studio.css").write_text("/* studio */")
    digest = hashlib.sha256(payload).hexdigest()
    (tmp_path / "ultimate-3d-studio-build.json").write_text(json.dumps({"sha256": digest}))
    monkeypatch.setattr(module, "ASSET_ROOT", tmp_path, raising=False)
    return module.RESOURCE_URL + "?v=" + digest


class DummyStorage:
    def __init__(self, entries=None):
        self.entries = list(entries or [])
        self.loaded = False
        self.creations = []
        self.updates = []

    async def async_get_info(self):
        self.loaded = True
        return {"resources": len(self.entries)}

    def async_items(self):
        assert self.loaded, "Lovelace resources must be loaded before inspection"
        return self.entries

    async def async_create_item(self, entry):
        assert self.loaded
        self.creations.append(dict(entry))
        item = {"id": "new-studio", "url": entry["url"], "type": entry["res_type"]}
        self.entries.append(item)
        return item

    async def async_update_item(self, item_id, updates):
        assert self.loaded
        self.updates.append((item_id, dict(updates)))
        for index, item in enumerate(self.entries):
            if item.get("id") == item_id:
                updated = {**item, "url": updates["url"], "type": updates["res_type"]}
                self.entries[index] = updated
                return updated
        raise KeyError(item_id)


@pytest.mark.asyncio
async def test_new_hacs_install_registers_exactly_one_module_in_storage_mode(packaged_assets):
    store = DummyStorage()
    lovelace = SimpleNamespace(resource_mode="storage", resources=store)
    first = await module.async_ensure_studio_lovelace_resource(lovelace)
    second = await module.async_ensure_studio_lovelace_resource(lovelace)
    assert first == "registered"
    assert second == "already_registered"
    assert store.creations == [
        {"url": packaged_assets, "res_type": "module"},
    ]
    assert all(item["type"] == "module" for item in store.entries)


@pytest.mark.asyncio
async def test_existing_current_build_is_not_duplicated_or_rewritten(packaged_assets):
    existing = {"id": "studio", "url": packaged_assets, "type": "module"}
    store = DummyStorage([existing])
    assert (
        await module.async_ensure_studio_lovelace_resource(
            SimpleNamespace(resource_mode="storage", resources=store)
        )
        == "already_registered"
    )
    assert store.entries == [existing]
    assert store.creations == []
    assert store.updates == []


@pytest.mark.asyncio
async def test_old_lovelace_url_updates_same_record_and_preserves_pcc_and_other_entries(packaged_assets):
    existing = {"id": "studio", "url": module.LEGACY_RESOURCE_URL + "?cache=old", "type": "module", "extra": "keep"}
    pcc = {"id": "pcc", "url": "/printer_control_center/printer-control-center-cards.js?v=old", "type": "module"}
    other = {"id": "other", "url": "/local/custom/ultimate-3d-studio.js", "type": "module"}
    store = DummyStorage([pcc, existing, other])
    assert (
        await module.async_ensure_studio_lovelace_resource(
            SimpleNamespace(resource_mode="storage", resources=store)
        )
        == "updated"
    )
    assert store.entries == [pcc, {**existing, "url": packaged_assets}, other]
    assert store.creations == []
    assert store.updates == [("studio", {"url": packaged_assets, "res_type": "module"})]


@pytest.mark.asyncio
async def test_packaged_url_updates_build_query_without_changing_identity(packaged_assets):
    existing = {"id": "studio", "url": module.RESOURCE_URL + "?v=old", "type": "module"}
    store = DummyStorage([existing])
    result = await module.async_ensure_studio_lovelace_resource(SimpleNamespace(resource_mode="storage", resources=store))
    assert result == "updated"
    assert store.entries == [{**existing, "url": packaged_assets}]
    assert store.creations == []


@pytest.mark.asyncio
@pytest.mark.parametrize("paths", [
    (module.LEGACY_RESOURCE_URL, module.RESOURCE_URL),
    (module.LEGACY_RESOURCE_URL, module.LEGACY_RESOURCE_URL),
    (module.RESOURCE_URL, module.RESOURCE_URL),
])
async def test_multiple_owned_resources_fail_closed_without_any_mutation(paths):
    entries = [{"id": str(index), "url": path + "?v=old", "type": "module"} for index, path in enumerate(paths)]
    store = DummyStorage(entries)
    result = await module.async_ensure_studio_lovelace_resource(SimpleNamespace(resource_mode="storage", resources=store))
    assert result == "studio_resource_conflict"
    assert store.entries == entries
    assert store.updates == []
    assert store.creations == []


@pytest.mark.asyncio
async def test_existing_owned_resource_without_id_is_not_replaced():
    entries = [{"url": module.LEGACY_RESOURCE_URL, "type": "module"}]
    store = DummyStorage(entries)
    result = await module.async_ensure_studio_lovelace_resource(SimpleNamespace(resource_mode="storage", resources=store))
    assert result == "resource_identity_invalid"
    assert store.entries == entries
    assert store.updates == []
    assert store.creations == []


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["ultimate-3d-studio.js", "ultimate-3d-studio.css", "ultimate-3d-studio-build.json"])
async def test_missing_packaged_asset_never_repoints_existing_resource(filename):
    (module.ASSET_ROOT / filename).unlink()
    entries = [{"id": "studio", "url": module.LEGACY_RESOURCE_URL, "type": "module"}]
    store = DummyStorage(entries)
    result = await module.async_ensure_studio_lovelace_resource(SimpleNamespace(resource_mode="storage", resources=store))
    assert result == "frontend_build_unavailable"
    assert store.entries == entries
    assert store.updates == []
    assert store.creations == []


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", ["not-json", "[]", '{"sha256":"../other"}', '{"sha256":"ABC"}'])
async def test_invalid_build_metadata_never_mutates_resource_storage(metadata):
    (module.ASSET_ROOT / "ultimate-3d-studio-build.json").write_text(metadata)
    store = DummyStorage()
    result = await module.async_ensure_studio_lovelace_resource(SimpleNamespace(resource_mode="storage", resources=store))
    assert result == "frontend_build_unavailable"
    assert store.updates == []
    assert store.creations == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [module.RESOURCE_URL, module.LEGACY_RESOURCE_URL])
async def test_wrong_resource_type_is_not_silently_overwritten(path):
    entries = [{"id": "studio", "url": path, "type": "js"}]
    store = DummyStorage(entries)
    result = await module.async_ensure_studio_lovelace_resource(
        SimpleNamespace(resource_mode="storage", resources=store)
    )
    assert result == "type_conflict"
    assert store.creations == []
    assert store.updates == []
    assert store.entries == entries


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
async def test_lovelace_late_loading_can_complete_registration_on_retry(packaged_assets):
    first = await module.async_ensure_studio_lovelace_resource(None)
    assert first == "lovelace_not_loaded"
    store = DummyStorage()
    result = await module.async_ensure_studio_lovelace_resource(
        SimpleNamespace(resource_mode="storage", resources=store)
    )
    assert result == "registered"
    assert store.entries == [{"id": "new-studio", "url": packaged_assets, "type": "module"}]
