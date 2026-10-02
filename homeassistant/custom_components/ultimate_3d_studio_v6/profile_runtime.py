"""Persistent canonical V6 profile catalog."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import re
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORE_VERSION = 1
STORE_KEY = "ultimate_3d_studio_v6.profiles"
DATA_PROFILE_RUNTIME = "profile_runtime"
PROFILE_KINDS = {"printer", "nozzle", "filament", "process", "build_plate"}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _profile(
    profile_id: str,
    kind: str,
    name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": profile_id,
        "kind": kind,
        "name": name,
        "source": "builtin",
        "payload": payload,
        "builtin": True,
        "created_at": "2026-07-04T00:00:00+00:00",
        "updated_at": "2026-07-07T00:00:00+00:00",
    }


def _plate(
    profile_id: str,
    name: str,
    surface: str,
    temperature_offset_c: int = 0,
) -> dict[str, Any]:
    return _profile(profile_id, "build_plate", name, {
        "surface": surface,
        "temperature_offset_c": temperature_offset_c,
        "width_mm": 256,
        "depth_mm": 256,
    })


BUILTIN_PROFILES: tuple[dict[str, Any], ...] = (
    _profile("printer.bambu_a1", "printer", "Bambu Lab A1", {
        "vendor": "Bambu Lab", "model": "A1", "technology": "FFF",
        "build_volume_mm": [256, 256, 256],
        "default_nozzle_profile_id": "nozzle.0_4_hardened",
    }),
    _profile("printer.bambu_x1c", "printer", "Bambu Lab X1 Carbon", {
        "vendor": "Bambu Lab", "model": "X1 Carbon", "technology": "FFF",
        "build_volume_mm": [256, 256, 256],
        "default_nozzle_profile_id": "nozzle.0_4_hardened",
    }),
    _profile("printer.bambu_p1s", "printer", "Bambu Lab P1S", {
        "vendor": "Bambu Lab", "model": "P1S", "technology": "FFF",
        "build_volume_mm": [256, 256, 256],
        "default_nozzle_profile_id": "nozzle.0_4_hardened",
    }),
    _profile("nozzle.0_2_stainless", "nozzle", "0,2 mm Edelstahl", {
        "diameter_mm": 0.2, "material": "stainless_steel",
    }),
    _profile("nozzle.0_4_hardened", "nozzle", "0,4 mm gehärteter Stahl", {
        "diameter_mm": 0.4, "material": "hardened_steel",
    }),
    _profile("nozzle.0_6_hardened", "nozzle", "0,6 mm gehärteter Stahl", {
        "diameter_mm": 0.6, "material": "hardened_steel",
    }),
    _profile("nozzle.0_8_hardened", "nozzle", "0,8 mm gehärteter Stahl", {
        "diameter_mm": 0.8, "material": "hardened_steel",
    }),
    _profile("process.0_08_extra_fine", "process", "0,08 mm Extra Fein", {
        "layer_height_mm": 0.08, "walls": 3,
        "infill_percent": 15, "speed_class": "quality",
    }),
    _profile("process.0_16_optimal", "process", "0,16 mm Optimal", {
        "layer_height_mm": 0.16, "walls": 3,
        "infill_percent": 15, "speed_class": "balanced",
    }),
    _profile("process.0_20_standard", "process", "0,20 mm Standard", {
        "layer_height_mm": 0.20, "walls": 3,
        "infill_percent": 15, "speed_class": "standard",
    }),
    _profile("process.0_28_draft", "process", "0,28 mm Entwurf", {
        "layer_height_mm": 0.28, "walls": 2,
        "infill_percent": 10, "speed_class": "draft",
    }),
    _plate("build_plate.textured_pei", "Texturierte PEI-Platte", "textured_pei"),
    _plate("build_plate.smooth_pei", "Smooth PEI Plate / High Temp Plate", "smooth_pei"),
    _plate("build_plate.cool_plate_super_tack", "Bambu Cool Plate SuperTack", "cool_plate_super_tack", -20),
    _plate("build_plate.cool_plate", "Cool Plate / PLA Plate", "cool_plate", -20),
    _plate("build_plate.engineering_plate", "Engineering Plate", "engineering_plate"),
    _plate("build_plate.high_temp_plate", "High Temp Plate", "high_temp_plate"),
    _plate("build_plate.smooth_cool_plate", "Bambu Smooth Cool Plate", "smooth_cool_plate", -15),
    _plate("build_plate.textured_cool_plate", "Bambu Textured Cool Plate", "textured_cool_plate", -15),
    _profile("filament.bambu_pla_basic", "filament", "Bambu PLA Basic", {
        "vendor": "Bambu Lab", "material": "PLA",
        "nozzle_temperature_c": [190, 240], "bed_temperature_c": 55,
        "max_volumetric_speed_mm3_s": 21,
    }),
    _profile("filament.bambu_petg_hf", "filament", "Bambu PETG HF", {
        "vendor": "Bambu Lab", "material": "PETG",
        "nozzle_temperature_c": [230, 260], "bed_temperature_c": 70,
        "max_volumetric_speed_mm3_s": 18,
    }),
    _profile("filament.generic_pla", "filament", "Generic PLA", {
        "vendor": "Generic", "material": "PLA",
        "nozzle_temperature_c": [190, 230], "bed_temperature_c": 55,
        "max_volumetric_speed_mm3_s": 12,
    }),
)

DEFAULT_SELECTION: dict[str, Any] = {
    "printer_profile_id": "printer.bambu_a1",
    "nozzle_profile_id": "nozzle.0_4_hardened",
    "process_profile_id": "process.0_20_standard",
    "build_plate_profile_id": "build_plate.textured_pei",
    "filament_profile_ids": ["filament.bambu_pla_basic"],
}

DEFAULT_CLOUD_STATUS: dict[str, Any] = {
    "configured": False,
    "syncing": False,
    "available_offline": False,
    "last_sync_at": None,
    "last_attempt_at": None,
    "last_error": None,
    "profile_count": 0,
    "credential_source": None,
}


class V6ProfileRuntime:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, STORE_KEY,
        )
        self._custom: list[dict[str, Any]] = []
        self._cloud: list[dict[str, Any]] = []
        self._hidden_profile_ids: set[str] = set()
        self._cloud_status = deepcopy(DEFAULT_CLOUD_STATUS)
        self._selection = deepcopy(DEFAULT_SELECTION)
        self._loaded = False

    async def async_load(self) -> None:
        if self._loaded:
            return
        stored = await self._store.async_load() or {}
        self._custom = [
            item for item in stored.get("custom_profiles", [])
            if isinstance(item, dict)
        ]
        self._cloud = [
            item for item in stored.get("cloud_profiles", [])
            if isinstance(item, dict)
        ]
        hidden = stored.get("hidden_profile_ids", [])
        self._hidden_profile_ids = {
            str(item) for item in hidden
            if isinstance(item, str) and item
        } if isinstance(hidden, list) else set()
        status = stored.get("cloud_sync", {})
        selection = stored.get("selection", {})
        if isinstance(status, dict):
            self._cloud_status.update(status)
        if isinstance(selection, dict):
            self._selection.update(selection)
        self._update_cloud_counts()
        self._validate_selection(self._selection)
        self._loaded = True

    def _all_profiles(self) -> list[dict[str, Any]]:
        return [*BUILTIN_PROFILES, *self._cloud, *self._custom]

    @staticmethod
    def _is_misclassified_print_profile(item: dict[str, Any]) -> bool:
        """Keep legacy local print presets out of the printer-profile selector."""
        if item.get("kind") != "printer" or item.get("source") != "local":
            return False
        payload = item.get("payload")
        if not isinstance(payload, dict):
            return False
        return any(key in payload for key in (
            "layer_height_mm", "first_layer_height_mm", "walls",
            "infill_percent", "speed_class", "outer_wall_speed_mm_s",
            "inner_wall_speed_mm_s",
        ))

    @staticmethod
    def _is_nozzle_specific_printer_profile(item: dict[str, Any]) -> bool:
        """Druckerprofile beschreiben nur den Drucker; die Düse ist ein eigenes Profil."""
        if item.get("kind") != "printer":
            return False
        payload = item.get("payload")
        return isinstance(payload, dict) and "nozzle_diameter_mm" in payload

    def _visible_profiles(self) -> list[dict[str, Any]]:
        return [
            item for item in self._all_profiles()
            if str(item.get("id")) not in self._hidden_profile_ids
            and not self._is_misclassified_print_profile(item)
            and not self._is_nozzle_specific_printer_profile(item)
        ]

    def _update_cloud_counts(self) -> None:
        visible_cloud = [
            item for item in self._cloud
            if str(item.get("id")) not in self._hidden_profile_ids
        ]
        self._cloud_status["available_offline"] = bool(visible_cloud)
        self._cloud_status["profile_count"] = len(visible_cloud)

    async def async_catalog(self) -> dict[str, Any]:
        await self.async_load()
        profiles = [deepcopy(item) for item in self._visible_profiles()]
        profiles.sort(key=lambda item: (
            str(item.get("kind")),
            {"bambu_cloud": 0, "local": 1, "builtin": 2}.get(
                str(item.get("source")), 9,
            ),
            str(item.get("name")).casefold(),
        ))
        return {
            "profiles": profiles,
            "groups": {
                kind: [
                    item for item in profiles
                    if item.get("kind") == kind
                ]
                for kind in sorted(PROFILE_KINDS)
            },
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

    async def async_replace_cloud_profiles(
        self,
        profiles: list[dict[str, Any]],
        status: dict[str, Any],
    ) -> dict[str, Any]:
        await self.async_load()
        normalized: list[dict[str, Any]] = []
        now = _now()
        for item in profiles:
            profile_id = str(item.get("id", "")).strip().lower()
            kind = str(item.get("kind", "")).strip().lower()
            name = str(item.get("name", "")).strip()
            payload = item.get("payload", {})
            if (
                not ID_PATTERN.fullmatch(profile_id)
                or kind not in PROFILE_KINDS
                or not name
                or not isinstance(payload, dict)
            ):
                continue
            normalized.append({
                "id": profile_id,
                "kind": kind,
                "name": name[:240],
                "source": "bambu_cloud",
                "payload": deepcopy(payload),
                "builtin": False,
                "cloud_managed": True,
                "created_at": str(item.get("created_at") or now),
                "updated_at": str(item.get("updated_at") or now),
                "cloud_id": str(item.get("cloud_id", "")),
                "cloud_type": str(item.get("cloud_type", "")),
                "base_id": item.get("base_id"),
                "version": item.get("version"),
            })
        self._cloud = normalized
        self._cloud_status = {
            **DEFAULT_CLOUD_STATUS,
            **status,
        }
        self._update_cloud_counts()
        self._validate_selection(self._selection)
        await self._save()
        return deepcopy(self._cloud_status)

    async def async_set_cloud_status(
        self,
        status: dict[str, Any],
    ) -> dict[str, Any]:
        await self.async_load()
        self._cloud_status = {
            **self._cloud_status,
            **status,
        }
        self._update_cloud_counts()
        await self._save()
        return deepcopy(self._cloud_status)

    async def async_set_selection(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        await self.async_load()
        next_selection = deepcopy(self._selection)
        for key in (
            "printer_profile_id",
            "nozzle_profile_id",
            "process_profile_id",
            "build_plate_profile_id",
        ):
            if key in payload:
                next_selection[key] = (
                    str(payload[key])
                    if payload[key] is not None else None
                )
        if "filament_profile_ids" in payload:
            value = payload["filament_profile_ids"]
            if not isinstance(value, list):
                raise ValueError("filament_profile_ids must be a list")
            next_selection["filament_profile_ids"] = [
                str(item) for item in value
            ]
        self._validate_selection(next_selection)
        self._selection = next_selection
        await self._save()
        return deepcopy(self._selection)

    async def async_upsert(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        await self.async_load()
        kind = str(payload.get("kind", "")).strip().lower()
        name = str(payload.get("name", "")).strip()
        profile_payload = payload.get("payload", {})
        profile_id = str(payload.get("id", "")).strip().lower()
        if kind not in PROFILE_KINDS:
            raise ValueError("unsupported profile kind")
        if not name or len(name) > 160:
            raise ValueError(
                "profile name must contain 1 to 160 characters",
            )
        if not isinstance(profile_payload, dict):
            raise ValueError("profile payload must be an object")
        if not profile_id:
            profile_id = f"custom.{kind}.{uuid4().hex}"
        if not ID_PATTERN.fullmatch(profile_id):
            raise ValueError("profile id contains invalid characters")
        if any(item["id"] == profile_id for item in BUILTIN_PROFILES):
            raise ValueError("builtin profiles cannot be overwritten")
        if any(item.get("id") == profile_id for item in self._cloud):
            raise ValueError(
                "Bambu Cloud profiles cannot be overwritten locally",
            )
        now = _now()
        existing = next((
            item for item in self._custom
            if item.get("id") == profile_id
        ), None)
        record = {
            "id": profile_id,
            "kind": kind,
            "name": name,
            "source": "local",
            "payload": deepcopy(profile_payload),
            "builtin": False,
            "created_at": (
                str(existing.get("created_at"))
                if existing else now
            ),
            "updated_at": now,
        }
        self._custom = [
            item for item in self._custom
            if item.get("id") != profile_id
        ]
        self._custom.append(record)
        self._hidden_profile_ids.discard(profile_id)
        await self._save()
        return deepcopy(record)

    async def async_remove(
        self,
        profile_id: str,
    ) -> dict[str, Any] | None:
        """Backward-compatible local-profile removal."""
        await self.async_load()
        for index, item in enumerate(self._custom):
            if str(item.get("id")) != profile_id:
                continue
            removed = self._custom.pop(index)
            self._remove_from_selection(profile_id)
            await self._save()
            return deepcopy(removed)
        return None

    async def async_remove_any(
        self,
        profile_id: str,
    ) -> dict[str, Any] | None:
        """Remove or persistently hide a profile from any profile category/source."""
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

        builtin = next((
            item for item in BUILTIN_PROFILES
            if str(item.get("id")) == profile_id
        ), None)
        if builtin is not None:
            self._hidden_profile_ids.add(profile_id)
            removed = deepcopy(builtin)
            removed["_removal_scope"] = "hidden_builtin_profile"
            self._remove_from_selection(profile_id)
            await self._save()
            return removed
        return None

    def _all_by_id(self) -> dict[str, dict[str, Any]]:
        return {
            str(item["id"]): item
            for item in self._visible_profiles()
        }

    def _first_profile_id(self, kind: str) -> str | None:
        candidates = sorted(
            (
                item for item in self._visible_profiles()
                if item.get("kind") == kind
            ),
            key=lambda item: (
                {"local": 0, "bambu_cloud": 1, "builtin": 2}.get(
                    str(item.get("source")), 9,
                ),
                str(item.get("name")).casefold(),
            ),
        )
        return str(candidates[0].get("id")) if candidates else None

    def _validate_selection(self, selection: dict[str, Any]) -> None:
        profiles = self._all_by_id()
        expected = {
            "printer_profile_id": "printer",
            "nozzle_profile_id": "nozzle",
            "process_profile_id": "process",
            "build_plate_profile_id": "build_plate",
        }
        for key, kind in expected.items():
            profile = profiles.get(str(selection.get(key)))
            if profile is not None and profile.get("kind") == kind:
                continue
            default_id = str(DEFAULT_SELECTION[key])
            default_profile = profiles.get(default_id)
            selection[key] = (
                default_id
                if default_profile is not None and default_profile.get("kind") == kind
                else self._first_profile_id(kind)
            )

        filament_ids = selection.get("filament_profile_ids", [])
        if not isinstance(filament_ids, list):
            filament_ids = []
        valid: list[str] = []
        for profile_id in filament_ids:
            normalized = str(profile_id)
            if normalized in valid:
                continue
            if profiles.get(normalized, {}).get("kind") == "filament":
                valid.append(normalized)
        if not valid:
            default_filament = str(DEFAULT_SELECTION["filament_profile_ids"][0])
            if profiles.get(default_filament, {}).get("kind") == "filament":
                valid = [default_filament]
            else:
                fallback = self._first_profile_id("filament")
                valid = [fallback] if fallback else []
        selection["filament_profile_ids"] = valid
        self._align_printer_profile_to_nozzle(selection, profiles)

    @staticmethod
    def _payload_number(profile: dict[str, Any] | None, key: str) -> float | None:
        payload = profile.get("payload") if isinstance(profile, dict) else None
        if not isinstance(payload, dict):
            return None
        try:
            value = float(payload.get(key))
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @staticmethod
    def _payload_text(profile: dict[str, Any] | None, key: str) -> str:
        payload = profile.get("payload") if isinstance(profile, dict) else None
        if not isinstance(payload, dict):
            return ""
        return str(payload.get(key) or "").strip().casefold()

    def _align_printer_profile_to_nozzle(
        self,
        selection: dict[str, Any],
        profiles: dict[str, dict[str, Any]],
    ) -> None:
        nozzle = profiles.get(str(selection.get("nozzle_profile_id")))
        selected_printer = profiles.get(str(selection.get("printer_profile_id")))
        nozzle_diameter = self._payload_number(nozzle, "diameter_mm")
        printer_diameter = self._payload_number(selected_printer, "nozzle_diameter_mm")
        if nozzle_diameter is None or printer_diameter is None:
            return
        if abs(nozzle_diameter - printer_diameter) < 0.001:
            return

        selected_vendor = self._payload_text(selected_printer, "vendor")
        selected_model = self._payload_text(selected_printer, "model")
        candidates = []
        for profile_id, profile in profiles.items():
            if profile.get("kind") != "printer":
                continue
            candidate_diameter = self._payload_number(profile, "nozzle_diameter_mm")
            if candidate_diameter is None or abs(candidate_diameter - nozzle_diameter) >= 0.001:
                continue
            vendor_score = 0 if self._payload_text(profile, "vendor") == selected_vendor else 1
            model_score = 0 if self._payload_text(profile, "model") == selected_model else 1
            source_score = {"local": 0, "bambu_cloud": 1, "builtin": 2}.get(str(profile.get("source")), 9)
            candidates.append((vendor_score, model_score, source_score, str(profile.get("name", "")).casefold(), profile_id))
        if candidates:
            selection["printer_profile_id"] = sorted(candidates)[0][4]

    def _remove_from_selection(self, profile_id: str) -> None:
        if profile_id in self._selection.get("filament_profile_ids", []):
            self._selection["filament_profile_ids"] = [
                item for item in self._selection.get("filament_profile_ids", [])
                if item != profile_id
            ]
        for key in (
            "printer_profile_id",
            "nozzle_profile_id",
            "process_profile_id",
            "build_plate_profile_id",
        ):
            if self._selection.get(key) == profile_id:
                self._selection[key] = None
        self._validate_selection(self._selection)

    async def _save(self) -> None:
        await self._store.async_save({
            "custom_profiles": self._custom,
            "cloud_profiles": self._cloud,
            "hidden_profile_ids": sorted(self._hidden_profile_ids),
            "cloud_sync": self._cloud_status,
            "selection": self._selection,
        })


def get_profile_runtime(hass: HomeAssistant) -> V6ProfileRuntime:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.get(DATA_PROFILE_RUNTIME)
    if not isinstance(runtime, V6ProfileRuntime):
        runtime = V6ProfileRuntime(hass)
        data[DATA_PROFILE_RUNTIME] = runtime
    return runtime