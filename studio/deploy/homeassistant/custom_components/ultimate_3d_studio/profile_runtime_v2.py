"""Extended canonical profile runtime with complete local profiles."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant

from .gcode_preset_contract import GCODE_DEFAULT_PROFILES, FILAMENT_GCODE_DEFAULTS
from .const import DOMAIN
from .h2s_profiles import H2S_PROFILES
from .curated_local_profiles import CURATED_LOCAL_PROFILES
from .manufacturer_profiles_complete import COMPLETE_MANUFACTURER_PROFILES
from .profile_catalog_enrichment import enrich_static_profiles
from .profile_runtime import BUILTIN_PROFILES, DATA_PROFILE_RUNTIME, StudioProfileRuntime

_RAW_STATIC_PROFILES: tuple[dict[str, Any], ...] = (
    *BUILTIN_PROFILES,
    *H2S_PROFILES,
    *GCODE_DEFAULT_PROFILES,
    *CURATED_LOCAL_PROFILES,
    *COMPLETE_MANUFACTURER_PROFILES,
)
STATIC_PROFILES = enrich_static_profiles(_RAW_STATIC_PROFILES)
for _profile in STATIC_PROFILES:
    if _profile.get("kind") == "filament" and _profile.get("source") != "bambu_cloud":
        for _key, _value in FILAMENT_GCODE_DEFAULTS.items():
            _profile["payload"].setdefault(_key, _value)
STATIC_PROFILE_IDS = {str(item.get("id")) for item in STATIC_PROFILES}
CANONICAL_A1_NOZZLE_PROFILE_IDS = {
    "local.nozzle.a1_0_2_stainless",
    "local.nozzle.a1_0_4_stainless",
    "local.nozzle.a1_0_6_stainless",
    "local.nozzle.a1_0_8_stainless",
    "local.nozzle.a1_0_4_hardened",
    "local.nozzle.a1_0_6_hardened",
    "local.nozzle.a1_0_8_hardened",
}


class StudioProfileRuntimeV2(StudioProfileRuntime):
    """Expose complete static, cloud and user profiles without cross-deletion."""

    def _all_profiles(self) -> list[dict[str, Any]]:
        return [*STATIC_PROFILES, *self._cloud, *self._custom]

    def _all_by_id(self) -> dict[str, dict[str, Any]]:
        return {str(item["id"]): item for item in self._visible_profiles()}

    def _visible_profiles(self) -> list[dict[str, Any]]:
        profiles = super()._visible_profiles()
        visible_ids = {str(item.get("id")) for item in profiles}
        if not CANONICAL_A1_NOZZLE_PROFILE_IDS.issubset(visible_ids):
            return profiles
        return [
            item for item in profiles
            if item.get("kind") != "nozzle"
            or str(item.get("id")) in CANONICAL_A1_NOZZLE_PROFILE_IDS
            or "a1" not in str((item.get("payload") or {}).get("printer") or (item.get("payload") or {}).get("printer_model") or "").casefold()
        ]

    async def async_catalog(self) -> dict[str, Any]:
        await self.async_load()
        profiles = [deepcopy(item) for item in self._visible_profiles()]
        profiles.sort(
            key=lambda item: (
                str(item.get("kind")),
                {"local": 0, "bambu_cloud": 1, "builtin": 2}.get(str(item.get("source")), 9),
                str(item.get("name")).casefold(),
            )
        )
        grouped = {
            kind: [item for item in profiles if item.get("kind") == kind]
            for kind in ("build_plate", "filament", "nozzle", "printer", "process")
        }
        return {
            "profiles": profiles,
            "groups": grouped,
            "selection": deepcopy(self._selection),
            "persistent": True,
            "custom_profiles_supported": True,
            "all_profile_sources_removable": True,
            "cloud_sync": deepcopy(self._cloud_status),
            "source_counts": {
                "builtin": sum(1 for item in profiles if item.get("source") == "builtin"),
                "bambu_cloud": sum(1 for item in profiles if item.get("source") == "bambu_cloud"),
                "local": sum(1 for item in profiles if item.get("source") == "local"),
            },
        }

    async def async_upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(payload.get("id", "")).strip().lower()
        if profile_id and profile_id in STATIC_PROFILE_IDS:
            raise ValueError("static profiles cannot be overwritten; save a copy instead")
        return await super().async_upsert(payload)

    async def async_remove_any(self, profile_id: str) -> dict[str, Any] | None:
        await self.async_load()
        for index, item in enumerate(self._custom):
            if str(item.get("id")) != profile_id:
                continue
            removed = deepcopy(self._custom.pop(index))
            removed["_removal_scope"] = "deleted_local_profile"
            self._remove_from_selection(profile_id)
            await self._save()
            return removed
        for item in self._cloud:
            if str(item.get("id")) != profile_id:
                continue
            self._hidden_profile_ids.add(profile_id)
            removed = deepcopy(item)
            removed["_removal_scope"] = "hidden_cloud_profile"
            self._remove_from_selection(profile_id)
            self._update_cloud_counts()
            await self._save()
            return removed
        static_profile = next((item for item in STATIC_PROFILES if str(item.get("id")) == profile_id), None)
        if static_profile is not None:
            self._hidden_profile_ids.add(profile_id)
            removed = deepcopy(static_profile)
            removed["_removal_scope"] = "hidden_curated_local_profile" if static_profile.get("source") == "local" else "hidden_builtin_profile"
            self._remove_from_selection(profile_id)
            await self._save()
            return removed
        return None


def install_profile_runtime_v2(hass: HomeAssistant) -> StudioProfileRuntimeV2:
    """Install the complete runtime before API views or cloud sync access it."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    runtime = domain_data.get(DATA_PROFILE_RUNTIME)
    if not isinstance(runtime, StudioProfileRuntimeV2):
        runtime = StudioProfileRuntimeV2(hass)
        domain_data[DATA_PROFILE_RUNTIME] = runtime
    return runtime