"""Persistent Studio profile and filament bank for Printer Control Center v5.

This module intentionally stores local Home Assistant Studio data only.
It does not depend on ha-bambulab, bambu_lab or any external Bambu integration.
Real slicing and direct printing remain disabled in the alpha series.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

STORAGE_VERSION = 1
STORAGE_KEY = "printer_control_center.studio_profiles"

BANK_VERSION = "5.0.0-beta38"


DEFAULT_PROFILE_BANK: dict[str, Any] = {
    "version": BANK_VERSION,
    "schema": 1,
    "source": "local",
    "notes": [
        "Local persistent Studio profile bank.",
        "Values are defaults/placeholders for planning and dry-run validation.",
        "Studio profile bank UI binding was added in alpha15.",
        "Profile selections are forwarded to dry-run jobs in alpha16.",
        "Dry-run result visualization was added in alpha17.",
        "Persistent Studio job plan structure was added in alpha18.",
        "Studio job UI reads studio_plan in alpha19.",
        "Studio health diagnostics were added in alpha20.",
        "Real slicing and direct printing are disabled.",
    ],
    "filaments": {
        "pla_basic": {
            "id": "pla_basic",
            "name": "PLA Basic",
            "material": "PLA",
            "vendor": "Generic",
            "nozzle_temp_c": 220,
            "bed_temp_c": 55,
            "max_volumetric_speed_mm3_s": 12,
            "enabled": True,
        },
        "petg_basic": {
            "id": "petg_basic",
            "name": "PETG Basic",
            "material": "PETG",
            "vendor": "Generic",
            "nozzle_temp_c": 250,
            "bed_temp_c": 75,
            "max_volumetric_speed_mm3_s": 10,
            "enabled": True,
        },
        "abs_basic": {
            "id": "abs_basic",
            "name": "ABS Basic",
            "material": "ABS",
            "vendor": "Generic",
            "nozzle_temp_c": 260,
            "bed_temp_c": 90,
            "max_volumetric_speed_mm3_s": 10,
            "enabled": True,
        },
        "asa_basic": {
            "id": "asa_basic",
            "name": "ASA Basic",
            "material": "ASA",
            "vendor": "Generic",
            "nozzle_temp_c": 260,
            "bed_temp_c": 90,
            "max_volumetric_speed_mm3_s": 10,
            "enabled": True,
        },
        "tpu_basic": {
            "id": "tpu_basic",
            "name": "TPU Basic",
            "material": "TPU",
            "vendor": "Generic",
            "nozzle_temp_c": 230,
            "bed_temp_c": 40,
            "max_volumetric_speed_mm3_s": 3,
            "enabled": True,
        },
    },
    "process_profiles": {
        "draft_020": {
            "id": "draft_020",
            "name": "Draft 0.20 mm",
            "layer_height_mm": 0.20,
            "wall_loops": 2,
            "top_shell_layers": 4,
            "bottom_shell_layers": 3,
            "sparse_infill_density_percent": 15,
            "sparse_infill_pattern": "grid",
            "support_enabled": False,
            "enabled": True,
        },
        "standard_020": {
            "id": "standard_020",
            "name": "Standard 0.20 mm",
            "layer_height_mm": 0.20,
            "wall_loops": 3,
            "top_shell_layers": 5,
            "bottom_shell_layers": 4,
            "sparse_infill_density_percent": 15,
            "sparse_infill_pattern": "gyroid",
            "support_enabled": False,
            "enabled": True,
        },
        "strength_020": {
            "id": "strength_020",
            "name": "Strength 0.20 mm",
            "layer_height_mm": 0.20,
            "wall_loops": 4,
            "top_shell_layers": 6,
            "bottom_shell_layers": 5,
            "sparse_infill_density_percent": 25,
            "sparse_infill_pattern": "gyroid",
            "support_enabled": False,
            "enabled": True,
        },
    },
    "printer_profiles": {
        "bambu_a1": {
            "id": "bambu_a1",
            "name": "Bambu Lab A1",
            "family": "A1",
            "build_plate_mm": {"x": 256, "y": 256, "z": 256},
            "default_nozzle_mm": 0.4,
            "enabled": True,
        },
        "bambu_p1": {
            "id": "bambu_p1",
            "name": "Bambu Lab P1 Series",
            "family": "P1",
            "build_plate_mm": {"x": 256, "y": 256, "z": 256},
            "default_nozzle_mm": 0.4,
            "enabled": True,
        },
        "bambu_x1": {
            "id": "bambu_x1",
            "name": "Bambu Lab X1 Series",
            "family": "X1",
            "build_plate_mm": {"x": 256, "y": 256, "z": 256},
            "default_nozzle_mm": 0.4,
            "enabled": True,
        },
        "bambu_h2": {
            "id": "bambu_h2",
            "name": "Bambu Lab H2 Series",
            "family": "H2",
            "build_plate_mm": {"x": 350, "y": 320, "z": 325},
            "default_nozzle_mm": 0.4,
            "enabled": True,
        },
    },
    "selection": {
        "printer_profile_id": "bambu_a1",
        "process_profile_id": "standard_020",
        "filament_profile_id": "pla_basic",
    },
}


def _store(hass: HomeAssistant) -> Store:
    return Store(hass, STORAGE_VERSION, STORAGE_KEY)


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def normalize_profile_bank(data: Any | None) -> dict[str, Any]:
    """Return a complete, safe profile bank structure."""
    base = deepcopy(DEFAULT_PROFILE_BANK)

    if not isinstance(data, dict):
        return base

    merged = _deep_merge(base, data)
    merged["version"] = BANK_VERSION
    merged["schema"] = 1
    merged["source"] = merged.get("source") or "local"

    for section in ("filaments", "process_profiles", "printer_profiles"):
        if not isinstance(merged.get(section), dict):
            merged[section] = deepcopy(DEFAULT_PROFILE_BANK[section])

    if not isinstance(merged.get("selection"), dict):
        merged["selection"] = deepcopy(DEFAULT_PROFILE_BANK["selection"])

    selection = merged["selection"]

    if selection.get("printer_profile_id") not in merged["printer_profiles"]:
        selection["printer_profile_id"] = DEFAULT_PROFILE_BANK["selection"]["printer_profile_id"]

    if selection.get("process_profile_id") not in merged["process_profiles"]:
        selection["process_profile_id"] = DEFAULT_PROFILE_BANK["selection"]["process_profile_id"]

    if selection.get("filament_profile_id") not in merged["filaments"]:
        selection["filament_profile_id"] = DEFAULT_PROFILE_BANK["selection"]["filament_profile_id"]

    return merged


async def async_load_profile_bank(hass: HomeAssistant) -> dict[str, Any]:
    """Load the persistent profile bank."""
    data = await _store(hass).async_load()
    return normalize_profile_bank(data)


async def async_save_profile_bank(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Save and return the normalized profile bank."""
    normalized = normalize_profile_bank(data)
    await _store(hass).async_save(normalized)
    return normalized


async def async_update_profile_bank(
    hass: HomeAssistant,
    patch: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply a partial patch to the persistent profile bank."""
    current = await async_load_profile_bank(hass)

    if not isinstance(patch, dict):
        patch = {}

    updated = _deep_merge(current, patch)
    return await async_save_profile_bank(hass, updated)


async def async_reset_profile_bank(hass: HomeAssistant) -> dict[str, Any]:
    """Reset the profile bank to alpha defaults."""
    data = normalize_profile_bank(None)
    await _store(hass).async_save(data)
    return data