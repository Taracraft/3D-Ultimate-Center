"""Fail-closed binding of the selected V6 process profile to native slicing."""
from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any


class ProcessProfileContractError(ValueError):
    """Raised when a selected process profile cannot be applied exactly."""


_LOCAL_SETTING_MAP = {
    "layer_height_mm": "layer_height",
    "first_layer_height_mm": "initial_layer_print_height",
    "walls": "wall_loops",
    "top_shell_layers": "top_shell_layers",
    "bottom_shell_layers": "bottom_shell_layers",
    "infill_percent": "sparse_infill_density",
    "outer_wall_speed_mm_s": "outer_wall_speed",
    "inner_wall_speed_mm_s": "inner_wall_speed",
    "travel_speed_mm_s": "travel_speed",
    "line_width_mm": "line_width",
    "outer_wall_line_width_mm": "outer_wall_line_width",
    "inner_wall_line_width_mm": "inner_wall_line_width",
    "top_surface_line_width_mm": "top_surface_line_width",
    "support_line_width_mm": "support_line_width",
    "sparse_infill_speed_mm_s": "sparse_infill_speed",
    "internal_solid_infill_speed_mm_s": "internal_solid_infill_speed",
    "top_surface_speed_mm_s": "top_surface_speed",
    "initial_layer_speed_mm_s": "initial_layer_speed",
    "bridge_speed_mm_s": "bridge_speed",
    "gap_infill_speed_mm_s": "gap_infill_speed",
    "solid_infill_speed_mm_s": "solid_infill_speed",
    "ironing_speed_mm_s": "ironing_speed",
    "support_speed_mm_s": "support_speed",
    "support_interface_speed_mm_s": "support_interface_speed",
    "bridge_flow_ratio": "bridge_flow",
    "support_top_z_distance_mm": "support_top_z_distance",
    "support_bottom_z_distance_mm": "support_bottom_z_distance",
    "support_object_xy_distance_mm": "support_object_xy_distance",
    "support_interface_spacing_mm": "support_interface_spacing",
    "support_interface_top_layers": "support_interface_top_layers",
    "support_interface_bottom_layers": "support_interface_bottom_layers",
    "infill_pattern": "infill_pattern",
    "wall_sequence": "wall_sequence",
    "seam_position": "seam_position",
    "acceleration_mm_s2": "acceleration",
    "jerk_mm_s": "jerk",
    "nozzle_temperature": "nozzle_temperature",
    "bed_temperature": "bed_temperature",
}
_ADVANCED_NUMERIC_RULES = {
    "line_width_mm": (0.01, False),
    "outer_wall_line_width_mm": (0.01, False),
    "inner_wall_line_width_mm": (0.01, False),
    "top_surface_line_width_mm": (0.01, False),
    "support_line_width_mm": (0.01, False),
    "sparse_infill_speed_mm_s": (1, False),
    "internal_solid_infill_speed_mm_s": (1, False),
    "top_surface_speed_mm_s": (1, False),
    "initial_layer_speed_mm_s": (1, False),
    "bridge_speed_mm_s": (1, False),
    "gap_infill_speed_mm_s": (1, False),
    "solid_infill_speed_mm_s": (1, False),
    "ironing_speed_mm_s": (1, False),
    "support_speed_mm_s": (1, False),
    "support_interface_speed_mm_s": (1, False),
    "bridge_flow_ratio": (0, False),
    "support_top_z_distance_mm": (0, False),
    "support_bottom_z_distance_mm": (0, False),
    "support_object_xy_distance_mm": (0, False),
    "support_interface_spacing_mm": (0, False),
    "support_interface_top_layers": (0, True),
    "support_interface_bottom_layers": (0, True),
    "acceleration_mm_s2": (100, False),
    "jerk_mm_s": (1, False),
    "nozzle_temperature": (180, False),
    "bed_temperature": (0, False),
}
_LOCAL_METADATA = {
    "speed_class",
    "profile_origin",
    "cloud_sync_protected",
    "slicing_supported",
    "compatible_nozzle_diameters_mm",
    "printer_vendor",
    "printer_model",
    "target_printer",
    "a1_specific",
    "nozzle_diameter_mm",
    "material_class",
}
_CLOUD_METADATA = {
    "_bambu_cloud",
    "updated_time",
    "print_settings_id",
    "print_extruder_id",
    "print_extruder_variant",
}
_SETTING_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


def _selected_process(catalog: dict[str, Any]) -> dict[str, Any]:
    selection = catalog.get("selection")
    profiles = catalog.get("profiles")
    if not isinstance(selection, dict) or not isinstance(profiles, list):
        raise ProcessProfileContractError(
            "Der Profilkatalog enthält keine gültige Prozessauswahl."
        )
    profile_id = str(selection.get("process_profile_id") or "")
    profile = next(
        (
            item
            for item in profiles
            if isinstance(item, dict)
            and str(item.get("id") or "") == profile_id
            and str(item.get("kind") or "") == "process"
        ),
        None,
    )
    if profile is None:
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil ist nicht verfügbar."
        )
    return profile


def _validate_json_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 12:
        raise ProcessProfileContractError(
            "Das Prozessprofil ist zu tief verschachtelt."
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProcessProfileContractError(
                "Das Prozessprofil enthält keine endliche Zahl."
            )
        return value
    if isinstance(value, list):
        if len(value) > 512:
            raise ProcessProfileContractError(
                "Das Prozessprofil enthält zu viele Listenwerte."
            )
        return [
            _validate_json_value(item, depth=depth + 1)
            for item in value
        ]
    if isinstance(value, dict):
        if len(value) > 512:
            raise ProcessProfileContractError(
                "Das Prozessprofil enthält zu viele Einstellungen."
            )
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not _SETTING_KEY.fullmatch(key):
                raise ProcessProfileContractError(
                    "Das Prozessprofil enthält einen ungültigen Einstellungsnamen."
                )
            result[key] = _validate_json_value(item, depth=depth + 1)
        return result
    raise ProcessProfileContractError(
        "Das Prozessprofil enthält einen nicht unterstützten Wert."
    )


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise ProcessProfileContractError(f"{label} ist ungültig.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ProcessProfileContractError(f"{label} ist ungültig.") from exc
    if not math.isfinite(parsed):
        raise ProcessProfileContractError(f"{label} ist ungültig.")
    return parsed


def _local_settings(
    payload: dict[str, Any],
    nozzle_contract: Any,
) -> dict[str, Any]:
    if payload.get("slicing_supported") is False:
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil ist nicht zum Slicing freigegeben."
        )

    vendor = str(payload.get("printer_vendor") or "").strip().casefold()
    if vendor and vendor.replace(" ", "") != "bambulab":
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil ist nicht für Bambu Lab freigegeben."
        )
    model = str(payload.get("printer_model") or "").strip().casefold()
    expected_model = getattr(nozzle_contract, "printer_model", "A1").casefold()
    if model and model != expected_model:
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil ist nicht für den Bambu Lab A1 freigegeben."
        )
    target = "".join(
        character
        for character in str(payload.get("target_printer") or "").casefold()
        if character.isalnum()
    )
    if target and target not in {expected_model, "bambulab" + expected_model}:
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil besitzt ein anderes Zieldruckermodell."
        )
    if payload.get("a1_specific") not in {None, expected_model == "a1"}:
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil ist nicht als A1-spezifisch freigegeben."
        )
    profile_nozzle = payload.get("nozzle_diameter_mm")
    if profile_nozzle is not None:
        diameter = _number(
            profile_nozzle,
            "Der Düsendurchmesser des Prozessprofils",
        )
        if not math.isclose(
            diameter,
            nozzle_contract.diameter_mm,
            abs_tol=1e-6,
        ):
            raise ProcessProfileContractError(
                "Das ausgewählte Prozessprofil passt nicht zum gewählten "
                "Düsendurchmesser."
            )

    empty_legacy_gcode = {
        key for key in ("start_sound_gcode", "end_sound_gcode", "custom_gcode_1", "custom_gcode_2")
        if isinstance(payload.get(key), str) and not payload[key].strip()
    }
    unknown = set(payload) - set(_LOCAL_SETTING_MAP) - _LOCAL_METADATA - empty_legacy_gcode
    if unknown:
        raise ProcessProfileContractError(
            "Das lokale Prozessprofil enthält noch nicht materialisierbare "
            "Einstellungen: " + ", ".join(sorted(unknown))
        )
    settings: dict[str, Any] = {}
    for source_key, native_key in _LOCAL_SETTING_MAP.items():
        if source_key not in payload:
            continue
        value: Any = payload[source_key]
        if source_key in _ADVANCED_NUMERIC_RULES:
            minimum, integer = _ADVANCED_NUMERIC_RULES[source_key]
            value = _number(value, source_key)
            if value < minimum or (integer and not value.is_integer()):
                raise ProcessProfileContractError(
                    f"{source_key}: gültige {'ganze ' if integer else ''}Zahl ab {minimum:g} erforderlich."
                )
            if integer:
                value = int(value)
        if source_key == "infill_percent":
            percent = _number(value, "Der Füllgrad")
            if not 0 <= percent <= 100:
                raise ProcessProfileContractError(
                    "Der Füllgrad muss zwischen 0 und 100 Prozent liegen."
                )
            value = f"{percent:g}%"
        settings[native_key] = value

    if "nozzle_temperature" in settings or "bed_temperature" in settings:
        raise ProcessProfileContractError("Düsen- und Betttemperaturen gehören in Filamentprofile, nicht in Prozessprofile.")
    first_layer = settings.get("initial_layer_print_height")
    if first_layer is not None:
        first_height = _number(first_layer, "Die Erstschichthöhe")
        if not nozzle_contract.min_layer_height_mm <= first_height <= nozzle_contract.diameter_mm:
            raise ProcessProfileContractError("Die Erstschichthöhe passt nicht zum gewählten Düsenbereich.")
    layer = settings.get("layer_height")
    if layer is not None:
        value = _number(layer, "Die Schichthöhe")
        if not (
            nozzle_contract.min_layer_height_mm
            <= value
            <= nozzle_contract.max_layer_height_mm
        ):
            raise ProcessProfileContractError(
                "Das gewählte Prozessprofil passt nicht zum Düsenbereich "
                f"{nozzle_contract.min_layer_height_mm:g}–"
                f"{nozzle_contract.max_layer_height_mm:g} mm."
            )
    if not settings:
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil enthält keine materialisierbaren Werte."
        )
    return settings


def _cloud_settings(
    payload: dict[str, Any],
    nozzle_contract: Any,
) -> dict[str, Any]:
    inherited = str(payload.get("inherits") or "").strip()
    expected = Path(nozzle_contract.process_profile).stem
    if inherited != expected:
        raise ProcessProfileContractError(
            "Das Bambu-Prozessprofil erbt nicht vom validierten Düsenprofil "
            f"'{expected}'."
        )
    settings = {
        key: value
        for key, value in payload.items()
        if key not in _CLOUD_METADATA and key != "inherits"
    }
    forbidden = {"printable_area", "printable_height", "bed_exclude_area", "extruder_offset", "gcode_flavor", "curr_bed_type"}
    for key in settings:
        if key in forbidden or key.startswith(("machine_", "filament_", "nozzle_")) or "plate_temp" in key or "gcode" in key.casefold():
            raise ProcessProfileContractError(f"{key}: Maschinen-, Filament- und G-Code-Werte gehören nicht in ein Prozessprofil.")
    if "layer_height" in settings:
        height = _number(settings["layer_height"], "Die Schichthöhe")
        if not nozzle_contract.min_layer_height_mm <= height <= nozzle_contract.max_layer_height_mm:
            raise ProcessProfileContractError("Das Cloud-Prozessprofil passt nicht zum gewählten Düsenbereich.")
    if "bed_temperature" in settings:
        raise ProcessProfileContractError("Betttemperaturen gehören in Filamentprofile, nicht in Prozessprofile.")
    if "initial_layer_print_height" in settings:
        height = _number(settings["initial_layer_print_height"], "Die Erstschichthöhe")
        if not nozzle_contract.min_layer_height_mm <= height <= nozzle_contract.diameter_mm:
            raise ProcessProfileContractError("Die Cloud-Erstschichthöhe passt nicht zum gewählten Düsenbereich.")
    # A Bambu cloud process profile may be a pure base-profile selection with
    # no overlay values. That must remain sliceable: the validated nozzle base
    # profile is the authority and the empty settings object means "use it as-is".
    return settings


def _contract_digest(contract: dict[str, Any]) -> str:
    return sha256(
        json.dumps(
            contract,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def resolve_selected_process_contract(
    catalog: dict[str, Any],
    nozzle_contract: Any,
) -> dict[str, Any]:
    """Resolve one exact selected process profile or reject it."""
    profile = _selected_process(catalog)
    payload = profile.get("payload")
    if not isinstance(payload, dict):
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil enthält keine gültigen Werte."
        )
    source = str(profile.get("source") or "")
    if source in {"builtin", "local"}:
        settings = _local_settings(payload, nozzle_contract)
        policy = "mapped_v6_process"
    elif source == "bambu_cloud":
        settings = _cloud_settings(payload, nozzle_contract)
        policy = "exact_bambu_cloud_overlay"
    else:
        raise ProcessProfileContractError(
            f"Die Prozessprofilquelle '{source or 'unbekannt'}' ist nicht "
            "für exaktes Slicing freigegeben."
        )

    safe_settings = _validate_json_value(settings)
    body = {
        "schema_version": 1,
        "profile_id": str(profile.get("id") or ""),
        "name": str(profile.get("name") or ""),
        "source": source,
        "materialization_policy": policy,
        "native_base_profile": nozzle_contract.process_profile,
        "settings": safe_settings,
    }
    if not body["profile_id"] or not body["name"]:
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil besitzt keine stabile ID oder keinen Namen."
        )
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > 256 * 1024:
        raise ProcessProfileContractError(
            "Das ausgewählte Prozessprofil ist größer als 256 KiB."
        )
    return {**body, "contract_sha256": _contract_digest(body)}



