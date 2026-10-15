"""Regression tests for the persistent Studio profile catalog."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


class FakeStore:
    def __init__(self, *_args, **_kwargs) -> None:
        self.data = None
        self.saved = []

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data
        self.saved.append(data)


homeassistant = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
ha_core = sys.modules.setdefault("homeassistant.core", types.ModuleType("homeassistant.core"))
ha_helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
ha_storage = sys.modules.setdefault(
    "homeassistant.helpers.storage",
    types.ModuleType("homeassistant.helpers.storage"),
)
ha_core.HomeAssistant = object
ha_storage.Store = FakeStore

package = sys.modules.setdefault(
    "ultimate_3d_studio",
    types.ModuleType("ultimate_3d_studio"),
)
package.__path__ = []
const = sys.modules.setdefault(
    "ultimate_3d_studio.const",
    types.ModuleType("ultimate_3d_studio.const"),
)
const.DOMAIN = "ultimate_3d_studio"

PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio"
    / "profile_runtime.py"
)
SPEC = importlib.util.spec_from_file_location(
    "ultimate_3d_studio.profile_runtime",
    PATH,
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


@pytest.mark.asyncio
async def test_catalog_contains_builtin_groups_and_default_selection() -> None:
    runtime = module.StudioProfileRuntime(object())
    catalog = await runtime.async_catalog()

    assert module.STORE_VERSION == 1
    assert catalog["persistent"] is True
    assert catalog["custom_profiles_supported"] is True
    assert catalog["all_profile_sources_removable"] is True
    assert catalog["selection"]["printer_profile_id"] == "printer.bambu_a1"
    assert catalog["selection"]["nozzle_profile_id"] == "nozzle.0_4_hardened"
    assert catalog["selection"]["process_profile_id"] == "process.0_20_standard"
    assert catalog["selection"]["filament_profile_ids"] == ["filament.bambu_pla_basic"]
    assert catalog["cloud_sync"]["available_offline"] is False
    assert catalog["source_counts"]["bambu_cloud"] == 0
    assert {item["id"] for item in catalog["groups"]["printer"]} >= {
        "printer.bambu_a1",
        "printer.bambu_x1c",
        "printer.bambu_p1s",
    }
    assert len(catalog["groups"]["nozzle"]) == 4


@pytest.mark.asyncio
async def test_selection_is_persisted_and_invalid_ids_fall_back() -> None:
    runtime = module.StudioProfileRuntime(object())

    selection = await runtime.async_set_selection(
        {
            "printer_profile_id": "printer.bambu_x1c",
            "process_profile_id": "process.0_16_optimal",
            "filament_profile_ids": ["filament.bambu_petg_hf"],
        }
    )

    assert selection["printer_profile_id"] == "printer.bambu_x1c"
    assert selection["process_profile_id"] == "process.0_16_optimal"
    assert selection["filament_profile_ids"] == ["filament.bambu_petg_hf"]
    assert runtime._store.saved[-1]["selection"] == selection

    fallback = await runtime.async_set_selection(
        {
            "printer_profile_id": "missing",
            "filament_profile_ids": ["missing"],
        }
    )
    assert fallback["printer_profile_id"] == "printer.bambu_a1"
    assert fallback["filament_profile_ids"] == ["filament.bambu_pla_basic"]


@pytest.mark.asyncio
async def test_custom_profile_can_be_created_selected_and_removed() -> None:
    runtime = module.StudioProfileRuntime(object())

    created = await runtime.async_upsert(
        {
            "kind": "process",
            "name": "Mein schneller Entwurf",
            "payload": {
                "layer_height_mm": 0.28,
                "walls": 2,
                "infill_percent": 8,
            },
        }
    )

    assert created["id"].startswith("custom.process.")
    assert created["builtin"] is False
    catalog = await runtime.async_catalog()
    assert any(item["id"] == created["id"] for item in catalog["groups"]["process"])

    selection = await runtime.async_set_selection({"process_profile_id": created["id"]})
    assert selection["process_profile_id"] == created["id"]

    removed = await runtime.async_remove_any(created["id"])
    assert removed is not None
    assert removed["id"] == created["id"]
    assert removed["_removal_scope"] == "deleted_local_profile"
    catalog = await runtime.async_catalog()
    assert catalog["selection"]["process_profile_id"] == "process.0_20_standard"
    assert all(item["id"] != created["id"] for item in catalog["profiles"])


@pytest.mark.asyncio
async def test_cloud_profiles_can_be_persistently_removed_from_local_catalog() -> None:
    runtime = module.StudioProfileRuntime(object())
    cloud_profiles = [
        {
            "id": "cloud.filament.pfus123",
            "kind": "filament",
            "name": "eSUN PLA+ Tara",
            "payload": {"inherits": "Generic PLA", "nozzle_temperature": "225"},
            "cloud_id": "PFUS123",
            "cloud_type": "filament",
            "base_id": "GFSA00",
            "version": "1.0",
        },
        {
            "id": "cloud.process.ppus456",
            "kind": "process",
            "name": "0.20mm Standard @ Tara",
            "payload": {"inherits": "0.20mm Standard @BBL A1"},
            "cloud_id": "PPUS456",
            "cloud_type": "print",
        },
    ]
    status = await runtime.async_replace_cloud_profiles(
        cloud_profiles,
        {"configured": True, "last_sync_at": "2026-07-04T19:00:00+00:00"},
    )

    assert status["available_offline"] is True
    assert status["profile_count"] == 2
    selection = await runtime.async_set_selection(
        {
            "filament_profile_ids": ["cloud.filament.pfus123"],
            "process_profile_id": "cloud.process.ppus456",
        }
    )
    assert selection["filament_profile_ids"] == ["cloud.filament.pfus123"]

    removed = await runtime.async_remove_any("cloud.filament.pfus123")
    assert removed is not None
    assert removed["_removal_scope"] == "hidden_cloud_profile"
    catalog = await runtime.async_catalog()
    assert all(item["id"] != "cloud.filament.pfus123" for item in catalog["profiles"])
    assert catalog["selection"]["filament_profile_ids"] == ["filament.bambu_pla_basic"]
    assert "cloud.filament.pfus123" in runtime._store.saved[-1]["hidden_profile_ids"]

    await runtime.async_replace_cloud_profiles(
        cloud_profiles,
        {"configured": True, "last_sync_at": "later"},
    )
    catalog = await runtime.async_catalog()
    assert all(item["id"] != "cloud.filament.pfus123" for item in catalog["profiles"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile_id", "kind", "selection_key"),
    [
        ("printer.bambu_a1", "printer", "printer_profile_id"),
        ("nozzle.0_4_hardened", "nozzle", "nozzle_profile_id"),
        ("filament.bambu_pla_basic", "filament", "filament_profile_ids"),
        ("process.0_20_standard", "process", "process_profile_id"),
        ("build_plate.textured_pei", "build_plate", "build_plate_profile_id"),
    ],
)
async def test_builtin_profile_from_every_category_can_be_hidden(
    profile_id: str,
    kind: str,
    selection_key: str,
) -> None:
    runtime = module.StudioProfileRuntime(object())
    removed = await runtime.async_remove_any(profile_id)

    assert removed is not None
    assert removed["kind"] == kind
    assert removed["_removal_scope"] == "hidden_builtin_profile"
    catalog = await runtime.async_catalog()
    assert all(item["id"] != profile_id for item in catalog["profiles"])
    assert profile_id in runtime._store.saved[-1]["hidden_profile_ids"]
    selected = catalog["selection"][selection_key]
    if isinstance(selected, list):
        assert profile_id not in selected
    else:
        assert selected != profile_id


@pytest.mark.asyncio
async def test_cloud_error_status_never_erases_last_good_profiles() -> None:
    runtime = module.StudioProfileRuntime(object())
    await runtime.async_replace_cloud_profiles(
        [{
            "id": "cloud.filament.pfus1",
            "kind": "filament",
            "name": "Persistentes Cloud-Filament",
            "payload": {"inherits": "Generic PLA"},
            "cloud_id": "PFUS1",
        }],
        {"configured": True, "last_sync_at": "2026-07-04T19:00:00+00:00"},
    )

    status = await runtime.async_set_cloud_status(
        {"last_error": "Cloud nicht erreichbar", "last_attempt_at": "later"}
    )
    catalog = await runtime.async_catalog()

    assert status["available_offline"] is True
    assert status["profile_count"] == 1
    assert catalog["source_counts"]["bambu_cloud"] == 1
    assert catalog["groups"]["filament"][0]["name"] == "Persistentes Cloud-Filament"


@pytest.mark.asyncio
async def test_load_keeps_old_version_one_document_and_adds_hidden_profile_state() -> None:
    runtime = module.StudioProfileRuntime(object())
    runtime._store.data = {
        "custom_profiles": [{
            "id": "custom.process.old",
            "kind": "process",
            "name": "Altes Profil",
            "source": "local",
            "payload": {},
            "builtin": False,
        }],
        "selection": {"process_profile_id": "custom.process.old"},
    }
    await runtime.async_load()
    catalog = await runtime.async_catalog()

    assert catalog["selection"]["process_profile_id"] == "custom.process.old"
    assert catalog["source_counts"]["local"] == 1
    assert catalog["source_counts"]["bambu_cloud"] == 0
    assert runtime._hidden_profile_ids == set()


@pytest.mark.asyncio
async def test_custom_profile_update_keeps_created_at() -> None:
    runtime = module.StudioProfileRuntime(object())
    first = await runtime.async_upsert(
        {
            "id": "custom.filament.test_pla",
            "kind": "filament",
            "name": "Test PLA",
            "payload": {"material": "PLA"},
        }
    )
    updated = await runtime.async_upsert(
        {
            "id": "custom.filament.test_pla",
            "kind": "filament",
            "name": "Test PLA Plus",
            "payload": {"material": "PLA+"},
        }
    )

    assert updated["created_at"] == first["created_at"]
    assert updated["name"] == "Test PLA Plus"
    catalog = await runtime.async_catalog()
    matches = [item for item in catalog["profiles"] if item["id"] == "custom.filament.test_pla"]
    assert len(matches) == 1


@pytest.mark.asyncio
async def test_builtin_profile_cannot_be_overwritten_but_can_be_hidden() -> None:
    runtime = module.StudioProfileRuntime(object())
    with pytest.raises(ValueError, match="builtin profiles"):
        await runtime.async_upsert(
            {
                "id": "process.0_20_standard",
                "kind": "process",
                "name": "Manipuliert",
                "payload": {},
            }
        )

    assert await runtime.async_remove("process.0_20_standard") is None
    assert await runtime.async_remove_any("process.0_20_standard") is not None


@pytest.mark.asyncio
async def test_invalid_profile_payloads_are_rejected() -> None:
    runtime = module.StudioProfileRuntime(object())

    with pytest.raises(ValueError, match="unsupported profile kind"):
        await runtime.async_upsert({"kind": "unknown", "name": "Test", "payload": {}})
    with pytest.raises(ValueError, match="profile name"):
        await runtime.async_upsert({"kind": "process", "name": "", "payload": {}})
    with pytest.raises(ValueError, match="profile payload"):
        await runtime.async_upsert({"kind": "process", "name": "Test", "payload": []})
    with pytest.raises(ValueError, match="invalid characters"):
        await runtime.async_upsert(
            {
                "id": "Invalid Profile ID",
                "kind": "process",
                "name": "Test",
                "payload": {},
            }
        )


@pytest.mark.asyncio
async def test_visible_builtin_a1_keeps_hardware_limits_without_duplicate_nozzle_profiles() -> None:
    runtime = module.StudioProfileRuntime(object())
    catalog = await runtime.async_catalog()
    a1 = next(p for p in catalog["profiles"] if p["id"] == "printer.bambu_a1")
    assert a1["payload"]["max_nozzle_temperature_c"] == 300
    assert a1["payload"]["max_bed_temperature_c"] == 100
    assert "nozzle_diameter_mm" not in a1["payload"]
    assert "default_nozzle_profile_id" not in a1["payload"]
