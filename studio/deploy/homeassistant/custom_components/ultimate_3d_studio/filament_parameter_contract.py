"""Shared native filament parameter mapping for preflight and the worker."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any

BED_TEMPERATURE_KEYS = {
    "Textured PEI Plate": "textured_plate_temp",
    "High Temp Plate": "hot_plate_temp",
    "Cool Plate": "cool_plate_temp",
    "Engineering Plate": "eng_plate_temp",
    "Supertack Plate": "supertack_plate_temp",
}

ALIASES = {
    "chamber_temperature_c": "chamber_temperatures",
    "flow_ratio": "filament_flow_ratio",
    "max_volumetric_speed_mm3_s": "filament_max_volumetric_speed",
    "density_g_cm3": "filament_density",
    "diameter_mm": "filament_diameter",
    "cooling_fan_min_percent": "fan_min_speed",
    "cooling_fan_max_percent": "fan_max_speed",
    "fan_full_speed_layer": "full_fan_speed_layer",
    "retraction_length_mm": "filament_retraction_length",
    "retraction_speed_mm_s": "filament_retraction_speed",
    "deretraction_speed_mm_s": "filament_deretraction_speed",
    "wipe_distance_mm": "filament_wipe_distance",
    "z_hop_mm": "filament_z_hop",
    "minimum_layer_time_s": "slow_down_layer_time",
    "overhang_fan_percent": "overhang_fan_speed",
}
TEMPERATURE_ALIASES = {
    "nozzle_temperature_c", "recommended_nozzle_temperature_c",
    "first_layer_nozzle_temperature_c", "bed_temperature_c",
    "first_layer_bed_temperature_c",
}
CURATED_KEYS = set(ALIASES) | TEMPERATURE_ALIASES | {
    "pressure_advance", "bridge_fan_percent", "first_layer_speed_mm_s",
}
# These values describe preparation or firmware calibration, rather than a
# native Bambu filament setting. Never advertise them as applied by the CLI.
ADVISORY_KEYS = {
    "pressure_advance", "drying_temperature_c", "drying_time_hours",
    "first_layer_speed_mm_s", "bridge_fan_percent",
}


def numbers(value: object, label: str) -> list[float]:
    values = value if isinstance(value, (list, tuple)) else [value]
    result = []
    for item in values:
        if isinstance(item, bool):
            raise ValueError(f"{label} ist ungültig.")
        try:
            number = float(item)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} ist ungültig.") from exc
        if not math.isfinite(number):
            raise ValueError(f"{label} ist ungültig.")
        result.append(number)
    if not result:
        raise ValueError(f"{label} enthält keinen Wert.")
    return result


def native_strings(value: object) -> list[str]:
    values = value if isinstance(value, (list, tuple)) else [value]
    return ["1" if v is True else "0" if v is False else str(v) for v in values]


def apply_filament_parameters(base: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Use native user keys first, then curated aliases, then native defaults."""
    result = deepcopy(base)
    prefixes = ("filament_", "nozzle_", "hot_plate_", "textured_plate_",
                "cool_plate_", "eng_plate_", "supertack_plate_", "chamber_")
    for key, value in payload.items():
        if key in CURATED_KEYS or key.startswith("_") or key in {
            "name", "type", "from", "instantiation", "inherits", "include",
            "compatible_printers", "setting_id", "filament_id",
        }:
            continue
        if key in result or key.startswith(prefixes):
            if isinstance(result.get(key), list) or key.startswith(prefixes):
                result[key] = native_strings(value)
            else:
                result[key] = "1" if value is True else "0" if value is False else str(value)
    for source, target in ALIASES.items():
        if source in payload and target not in payload:
            result[target] = native_strings(payload[source])
    scalar_nozzle = payload.get("nozzle_temperature_c")
    if isinstance(scalar_nozzle, (list, tuple)):
        bounds = numbers(scalar_nozzle, "nozzle_temperature_c")
        if len(bounds) != 2 or bounds[0] > bounds[1]:
            raise ValueError("Der Düsentemperaturbereich benötigt eine geordnete Unter- und Obergrenze.")
        for key, value in zip(("nozzle_temperature_range_low", "nozzle_temperature_range_high"), bounds, strict=True):
            if key not in payload:
                result[key] = [f"{value:g}"]
        scalar_nozzle = None  # A range is a constraint, not a setpoint.
    normal = scalar_nozzle if scalar_nozzle is not None else payload.get("recommended_nozzle_temperature_c")
    initial = payload.get("first_layer_nozzle_temperature_c", normal)
    for key, value in (("nozzle_temperature", normal), ("nozzle_temperature_initial_layer", initial)):
        if key not in payload and value is not None:
            result[key] = native_strings(value)
    bed = payload.get("bed_temperature_c")
    first_bed = payload.get("first_layer_bed_temperature_c", bed)
    # Cool/SuperTack temperatures use the native surface-specific authority.
    # A generic hot-plate recommendation must not enable an unsupported plate.
    for prefix in ("hot_plate_temp", "textured_plate_temp", "eng_plate_temp"):
        for key, value in ((prefix, bed), (prefix + "_initial_layer", first_bed)):
            supported = key in base and min(numbers(base[key], key)) > 0
            if key not in payload and value is not None and supported:
                result[key] = native_strings(value)
    validate_filament_parameters(result)
    return result


def validate_filament_parameters(profile: dict[str, Any]) -> None:
    for key in {"nozzle_temperature", "nozzle_temperature_initial_layer", "nozzle_temperature_range_low", "nozzle_temperature_range_high"} | {
        key + suffix for key in BED_TEMPERATURE_KEYS.values()
        for suffix in ("", "_initial_layer")
    }:
        if key in profile:
            values = numbers(profile[key], key)
            if min(values) < 0 or any(not value.is_integer() for value in values):
                raise ValueError(f"{key} benötigt eine nichtnegative ganze Temperatur in °C.")
    if "nozzle_temperature_range_low" in profile and "nozzle_temperature_range_high" in profile:
        low = min(numbers(profile["nozzle_temperature_range_low"], "nozzle_temperature_range_low"))
        high = max(numbers(profile["nozzle_temperature_range_high"], "nozzle_temperature_range_high"))
        if low > high:
            raise ValueError("Der native Düsentemperaturbereich ist ungültig.")
        for key in ("nozzle_temperature", "nozzle_temperature_initial_layer"):
            if key in profile and any(value < low or value > high for value in numbers(profile[key], key)):
                raise ValueError(f"{key} liegt außerhalb des gewählten Filament-Temperaturbereichs.")
    for key in ("fan_min_speed", "fan_max_speed", "overhang_fan_speed"):
        if key in profile and any(v < 0 or v > 100 for v in numbers(profile[key], key)):
            raise ValueError(f"{key} muss zwischen 0 und 100 liegen.")
    if "fan_min_speed" in profile and "fan_max_speed" in profile:
        if max(numbers(profile["fan_min_speed"], "fan_min_speed")) > min(numbers(profile["fan_max_speed"], "fan_max_speed")):
            raise ValueError("Die minimale Lüftergeschwindigkeit überschreitet die maximale.")
    for key in ("filament_diameter", "filament_flow_ratio", "filament_max_volumetric_speed", "filament_density"):
        if key in profile and min(numbers(profile[key], key)) <= 0:
            raise ValueError(f"{key} muss größer als null sein.")
    for key in ("filament_retraction_length", "filament_retraction_speed", "filament_deretraction_speed",
                "filament_wipe_distance", "filament_z_hop", "full_fan_speed_layer", "slow_down_layer_time"):
        value = profile.get(key)
        if value == "nil" or isinstance(value, list) and value and all(v == "nil" for v in value):
            continue  # Native nullable filament overrides inherit the machine.
        if key in profile and min(numbers(value, key)) < 0:
            raise ValueError(f"{key} darf nicht negativ sein.")


@lru_cache(maxsize=1)
def native_filament_authorities() -> dict[str, Any]:
    data = json.loads(Path(__file__).with_name("native_filament_defaults.json").read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("profiles"), dict):
        raise ValueError("Die native Filamentautorität ist ungültig.")
    try:
        from .printer_model_contract import h2s_defaults
    except ImportError:
        def h2s_defaults():
            return json.loads(Path(__file__).with_name("h2s_native_defaults.json").read_text())
    return {**data["profiles"], **h2s_defaults()["filaments"]}


def preflight_filament_settings(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("inherits") or payload.get("native_profile_name") or "").strip().strip('"')
    authority = native_filament_authorities().get(name)
    if not isinstance(authority, dict):
        raise ValueError("Für das Filamentprofil fehlt eine geprüfte native Parameterautorität.")
    settings = authority["settings"]
    if "H2S" in name:
        settings = {k: [v[0]] if isinstance(v, list) and v else v for k,v in settings.items()}
    return apply_filament_parameters(settings, payload)


def check_filament_temperatures(profile: dict[str, Any], limits: dict[str, Any], bed_type: str) -> dict[str, list[float]]:
    result = {}
    bed_key = BED_TEMPERATURE_KEYS.get(bed_type)
    if bed_type and bed_key is None:
        raise ValueError(f"Der native Plattentyp {bed_type} besitzt keinen geprüften Temperaturvertrag.")
    for key in ("nozzle_temperature", "nozzle_temperature_initial_layer"):
        values = numbers(profile.get(key), key)
        if min(values) <= 0 or max(values) > float(limits["max_nozzle_temperature_c"]):
            raise ValueError(f"{key} überschreitet die zulässige Düsentemperatur des gewählten Druckers.")
        result[key] = values
    for key in ("nozzle_temperature_range_low", "nozzle_temperature_range_high"):
        if key in profile and max(numbers(profile[key], key)) > float(limits["max_nozzle_temperature_c"]):
            raise ValueError(f"{key} überschreitet die zulässige Düsentemperatur des gewählten Druckers.")
    for prefix in BED_TEMPERATURE_KEYS.values():
        for key in (prefix, prefix + "_initial_layer"):
            if key in profile and max(numbers(profile[key], key)) > float(limits["max_bed_temperature_c"]):
                raise ValueError(f"{key} überschreitet die zulässige Betttemperatur des gewählten Druckers.")
    if "max_chamber_temperature_c" not in limits and "chamber_temperatures" in profile:
        values = numbers(profile["chamber_temperatures"], "chamber_temperatures")
        if any(v != 0 for v in values):
            raise ValueError("Dieser Drucker besitzt keinen geprüften Kammerheizer.")
    if "max_chamber_temperature_c" in limits:
        values = numbers(profile.get("chamber_temperatures", ["0"]), "chamber_temperatures")
        if min(values) < 0 or max(values) > float(limits["max_chamber_temperature_c"]):
            raise ValueError("Die Kammertemperatur überschreitet die Druckergrenze.")
        result["chamber_temperatures"] = values
    if bed_key:
        for key in (bed_key, bed_key + "_initial_layer"):
            values = numbers(profile.get(key), key)
            if min(values) <= 0:
                raise ValueError(f"Das native Filamentprofil unterstützt {bed_type} nicht (Betttemperatur 0 °C).")
            result[key] = values
    return result


def parameter_proof(profile: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    keys = set(ALIASES.values()) | {"filament_type", "nozzle_temperature", "nozzle_temperature_initial_layer",
                                  "nozzle_temperature_range_low", "nozzle_temperature_range_high"}
    keys |= {k + suffix for k in BED_TEMPERATURE_KEYS.values() for suffix in ("", "_initial_layer")}
    if str(payload.get("printer_model") or "").casefold() != "h2s":
        keys.discard("chamber_temperatures")
    keys |= {key for key in payload if key in profile and key not in CURATED_KEYS
             and (key.startswith(("filament_", "nozzle_")) or key in {"slow_down_for_layer_cooling"})
             and "gcode" not in key}
    return {"parameter_settings": {key: deepcopy(profile[key]) for key in sorted(keys)
                                    if key in profile and profile[key] not in ("nil", ["nil"])},
            "advisory_parameters": sorted(ADVISORY_KEYS & set(payload))}


def validate_shared_bed_temperatures(profiles: list[dict[str, Any]], bed_type: str) -> None:
    """A single heated bed cannot execute different per-material targets."""
    key = BED_TEMPERATURE_KEYS.get(bed_type)
    if len(profiles) < 2 or key is None:
        return
    for parameter in (key, key + "_initial_layer"):
        targets = [numbers(profile.get(parameter), parameter)[0] for profile in profiles]
        if any(abs(value - targets[0]) > 1e-6 for value in targets[1:]):
            raise ValueError("Die Materialprofile verlangen unterschiedliche Betttemperaturen. Für das gemeinsame Druckbett müssen alle gewählten Filamentprofile für diese Platte dieselben Normal- und Erstschichttemperaturen festlegen.")
