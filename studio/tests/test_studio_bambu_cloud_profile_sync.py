"""Regression tests for read-only Bambu Cloud profile synchronization."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


homeassistant = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
ha_config_entries = sys.modules.setdefault(
    "homeassistant.config_entries",
    types.ModuleType("homeassistant.config_entries"),
)
ha_core = sys.modules.setdefault("homeassistant.core", types.ModuleType("homeassistant.core"))
ha_helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
ha_aiohttp = sys.modules.setdefault(
    "homeassistant.helpers.aiohttp_client",
    types.ModuleType("homeassistant.helpers.aiohttp_client"),
)
ha_event = sys.modules.setdefault(
    "homeassistant.helpers.event",
    types.ModuleType("homeassistant.helpers.event"),
)
ha_config_entries.ConfigEntry = object
ha_core.HomeAssistant = object
ha_aiohttp.async_get_clientsession = lambda _hass: None
ha_event.async_track_time_interval = lambda *_args, **_kwargs: (lambda: None)

package = sys.modules.setdefault(
    "ultimate_3d_studio",
    types.ModuleType("ultimate_3d_studio"),
)
package.__path__ = []
const = sys.modules.setdefault(
    "ultimate_3d_studio.const",
    types.ModuleType("ultimate_3d_studio.const"),
)
for key, value in {
    "CONF_CLOUD_ACCESS_TOKEN": "cloud_access_token",
    "CONF_CLOUD_EMAIL": "cloud_email",
    "CONF_CLOUD_ENABLED": "cloud_enabled",
    "CONF_CLOUD_PROFILE_SYNC": "cloud_profile_sync",
    "CONF_CLOUD_REFRESH_TOKEN": "cloud_refresh_token",
    "CONF_CLOUD_REGION": "cloud_region",
    "CONF_CLOUD_UID": "cloud_uid",
    "DATA_CLOUD_PROFILE_SYNC": "cloud_profile_sync_runtime",
    "DEFAULT_CLOUD_PROFILE_SYNC": True,
    "DOMAIN": "ultimate_3d_studio",
    "REGION_CHINA": "china",
    "REGION_GLOBAL": "global",
    "VERSION": "6.0.0-test",
}.items():
    setattr(const, key, value)

profile_runtime = sys.modules.setdefault(
    "ultimate_3d_studio.profile_runtime",
    types.ModuleType("ultimate_3d_studio.profile_runtime"),
)
profile_runtime.get_profile_runtime = lambda _hass: None

PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio"
    / "bambu_cloud_profile_sync.py"
)
SPEC = importlib.util.spec_from_file_location(
    "ultimate_3d_studio.bambu_cloud_profile_sync",
    PATH,
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_preset_id_extraction_supports_nested_response_shapes() -> None:
    payload = {
        "data": {
            "settings": [
                "PFUS123",
                {"setting_id": "PPUS456"},
                {"id": "PMUS789"},
                "GFSA00",
                "PFUS123",
            ]
        }
    }
    assert module._preset_ids(payload) == ["PFUS123", "PPUS456", "PMUS789"]


@pytest.mark.parametrize(
    ("preset_id", "profile_type", "expected_kind"),
    [
        ("PFUS123", "filament", "filament"),
        ("PPUS123", "print", "process"),
        ("PMUS123", "printer", "printer"),
    ],
)
def test_profile_record_maps_cloud_types_and_preserves_full_setting(
    preset_id: str,
    profile_type: str,
    expected_kind: str,
) -> None:
    record = module._profile_record(
        preset_id,
        {
            "type": profile_type,
            "name": "Mein Profil",
            "version": "1.5",
            "base_id": "GFSA00",
            "update_time": "2026-07-04 19:00:00",
            "setting": {
                "inherits": "Bambu PLA Basic",
                "nozzle_temperature": "225,220",
            },
        },
    )
    assert record is not None
    assert record["kind"] == expected_kind
    assert record["id"] == f"cloud.{expected_kind}.{preset_id.lower()}"
    assert record["payload"]["inherits"] == "Bambu PLA Basic"
    assert record["payload"]["_bambu_cloud"]["preset_id"] == preset_id
    assert record["cloud_id"] == preset_id


def test_studio_client_identification_is_explicit_and_not_bambu_studio() -> None:
    headers = module.BambuCloudProfileSync._headers("")
    assert headers["X-BBL-Client-Name"] == "Ultimate3DStudio"
    assert headers["X-BBL-Client-Type"] == "integration"
    assert all("BambuStudio" not in value for value in headers.values())


@pytest.mark.asyncio
async def test_failed_detail_fetch_keeps_cached_profile() -> None:
    sync = module.BambuCloudProfileSync(object(), SimpleNamespace(data={}, options={}))

    async def fake_detail(preset_id: str, _credential: str, _region: str):
        if preset_id == "PFUS_OK":
            return {
                "type": "filament",
                "name": "Fresh",
                "setting": {"inherits": "Generic PLA"},
            }
        raise RuntimeError("temporary failure")

    sync._async_fetch_detail = fake_detail
    profiles, failed = await sync._async_fetch_profiles(
        ["PFUS_OK", "PPUS_FAIL"],
        "",
        "global",
        {
            "PPUS_FAIL": {
                "id": "cloud.process.ppus_fail",
                "kind": "process",
                "name": "Cached Process",
                "payload": {"inherits": "0.20mm Standard"},
                "cloud_id": "PPUS_FAIL",
                "cloud_type": "print",
                "updated_at": "old",
            }
        },
    )

    assert failed == 1
    assert {item["name"] for item in profiles} == {"Fresh", "Cached Process"}


def test_detail_payload_accepts_wrapped_and_direct_objects() -> None:
    direct = {"type": "filament", "name": "Direct", "setting": {}}
    wrapped = {"data": {"type": "print", "name": "Wrapped", "setting": {}}}
    assert module._detail_payload(direct)["name"] == "Direct"
    assert module._detail_payload(wrapped)["name"] == "Wrapped"


@pytest.mark.asyncio
async def test_non_a1_filament_inheritance_is_preserved_without_bambu_lookup() -> None:
    sync = module.BambuCloudProfileSync(
        object(),
        SimpleNamespace(data={}, options={}),
    )
    called = False

    async def forbidden_lookup(_name: str):
        nonlocal called
        called = True
        raise AssertionError("non-A1 inheritance must not use the Bambu system catalog")

    sync._async_resolve_system_filament = forbidden_lookup
    profile = {
        "id": "cloud.filament.sunlu_ad3",
        "kind": "filament",
        "name": "SUNLU PLA+ 2.0 @FF AD3 - Tara",
        "source": "bambu_cloud",
        "payload": {
            "inherits": "SUNLU PLA+ 2.0 @FF AD3",
            "nozzle_temperature": ["220"],
        },
    }
    result = await sync._async_expand_filament_profile(profile)

    assert called is False
    assert result["payload"]["inherits"] == "SUNLU PLA+ 2.0 @FF AD3"
    assert result["payload"]["slicing_supported"] is False
    assert (
        result["payload"]["bambu_a1_compatibility"]
        == "unsupported_printer_profile"
    )
    assert result["payload"]["_studio_inheritance"] == {
        "resolved": False,
        "base_profile": "SUNLU PLA+ 2.0 @FF AD3",
        "reason": "non_a1_base_profile",
    }
    assert result["compatibility_status"] == "unsupported_target_printer"


@pytest.mark.asyncio
async def test_a1_filament_inheritance_still_uses_system_catalog() -> None:
    sync = module.BambuCloudProfileSync(
        object(),
        SimpleNamespace(data={}, options={}),
    )

    async def resolve(name: str):
        assert name == "Generic PLA @BBL A1"
        return {
            "name": "Generic PLA @BBL A1",
            "filament_type": ["PLA"],
            "nozzle_temperature": ["220"],
        }

    sync._async_resolve_system_filament = resolve
    profile = {
        "id": "cloud.filament.a1",
        "kind": "filament",
        "name": "Mein A1 PLA",
        "source": "bambu_cloud",
        "payload": {
            "inherits": "Generic PLA @BBL A1",
            "filament_max_volumetric_speed": ["18"],
        },
    }
    result = await sync._async_expand_filament_profile(profile)

    assert result["inheritance_resolved"] is True
    assert result["payload"]["filament_type"] == ["PLA"]
    assert result["payload"]["filament_max_volumetric_speed"] == ["18"]


def test_unknown_profile_type_is_ignored() -> None:
    assert module._profile_record(
        "UNKNOWN",
        {"type": "other", "name": "Unsupported", "setting": {}},
    ) is None
