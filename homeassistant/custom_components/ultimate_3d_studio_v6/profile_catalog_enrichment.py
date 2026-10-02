"""Normalize and validate complete local filament profiles for Bambu Lab A1."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

REQUIRED_FILAMENT_FIELDS = {
    "vendor", "material", "sub_brand", "diameter_mm",
    "nozzle_temperature_c", "recommended_nozzle_temperature_c",
    "first_layer_nozzle_temperature_c", "bed_temperature_c",
    "first_layer_bed_temperature_c", "max_volumetric_speed_mm3_s",
    "flow_ratio", "cooling_fan_min_percent", "cooling_fan_max_percent",
    "fan_full_speed_layer", "retraction_length_mm", "retraction_speed_mm_s",
    "deretraction_speed_mm_s", "wipe_distance_mm", "z_hop_mm",
    "pressure_advance", "enclosure", "abrasive",
    "hardened_nozzle_required", "drying_temperature_c",
    "drying_time_hours", "target_printer", "printer_vendor",
    "printer_model", "a1_specific", "bambu_a1_compatibility",
    "cloud_sync_protected", "slicing_supported", "native_profile_name",
}


def _material_family(payload: dict[str, Any]) -> str:
    return str(payload.get("material", "")).upper()


def _is_flexible(material: str) -> bool:
    return any(token in material for token in ("TPU", "TPE", "PEBA"))


def _is_petg(material: str) -> bool:
    return "PETG" in material or material.startswith("PET-")


def _is_high_temp(material: str) -> bool:
    return any(token in material for token in ("ABS", "ASA", "PA", "NYLON", "PC", "PEEK", "PP", "HIPS"))


def _is_support(material: str) -> bool:
    return any(token in material for token in ("PVA", "SUPPORT", "HIPS"))


def _default_drying(material: str) -> tuple[int, int]:
    if "PEEK" in material:
        return 120, 12
    if any(token in material for token in ("PA", "NYLON", "PC")):
        return 85, 12
    if any(token in material for token in ("ABS", "ASA", "HIPS")):
        return 70, 8
    if _is_petg(material):
        return 60, 8
    if _is_flexible(material):
        return 55, 8
    if "PVA" in material:
        return 55, 10
    return 45, 5


def _native_profile_name(material: str) -> str:
    if _is_petg(material) or material.startswith("PET-"):
        return "Generic PETG HF @BBL A1"
    if "PLA" in material:
        return "Generic PLA @BBL A1"
    if "ASA" in material:
        return "Generic ASA @BBL A1"
    if "ABS" in material:
        return "Generic ABS @BBL A1"
    if _is_flexible(material):
        return "Generic TPU @BBL A1"
    if "PA" in material or "NYLON" in material:
        return "Generic PA @BBL A1"
    if "PC" in material:
        return "Generic PC @BBL A1"
    if "PVA" in material or "SUPPORT" in material:
        return "Generic PVA @BBL A1"
    if "HIPS" in material:
        return "Generic HIPS @BBL A1"
    if "PP" in material:
        return "Generic PP @BBL A1"
    if "PVB" in material:
        return "Generic PLA @BBL A1"
    return ""


def _compatibility(payload: dict[str, Any]) -> str:
    nozzle_range = payload.get("nozzle_temperature_c", [0, 0])
    nozzle_max = max(nozzle_range) if isinstance(nozzle_range, list) and nozzle_range else 0
    bed = float(payload.get("bed_temperature_c", 0) or 0)
    if nozzle_max > 300 or bed > 100:
        return "unsupported_temperature_limits"
    if str(payload.get("enclosure")) == "required":
        return "limited_open_frame"
    return "supported"


def enrich_filament_profile(profile: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(profile)
    if result.get("kind") != "filament" or result.get("source") != "local":
        return result
    payload = result.setdefault("payload", {})
    material = _material_family(payload)
    nozzle = payload.get("nozzle_temperature_c", [200, 220])
    if not isinstance(nozzle, list) or len(nozzle) != 2:
        nozzle = [200, 220]
        payload["nozzle_temperature_c"] = nozzle
    recommended = int(payload.get("recommended_nozzle_temperature_c") or round((float(nozzle[0]) + float(nozzle[1])) / 2))
    bed = int(payload.get("bed_temperature_c") or 0)
    dry_temp, dry_hours = _default_drying(material)
    compatibility = _compatibility(payload)
    native_name = _native_profile_name(material)

    payload.setdefault("recommended_nozzle_temperature_c", recommended)
    payload.setdefault("first_layer_nozzle_temperature_c", min(int(nozzle[1]), recommended + 5))
    payload.setdefault("first_layer_bed_temperature_c", bed + (5 if bed > 0 else 0))
    payload.setdefault("flow_ratio", 0.98 if _is_petg(material) else 1.0)
    payload.setdefault("fan_full_speed_layer", 3 if not _is_high_temp(material) else 5)
    if _is_flexible(material):
        payload.setdefault("retraction_length_mm", 0.4)
        payload.setdefault("retraction_speed_mm_s", 20)
        payload.setdefault("deretraction_speed_mm_s", 20)
        payload.setdefault("wipe_distance_mm", 0.5)
        payload.setdefault("z_hop_mm", 0.0)
        payload.setdefault("pressure_advance", 0.035)
    elif _is_petg(material):
        payload.setdefault("retraction_length_mm", 0.8)
        payload.setdefault("retraction_speed_mm_s", 30)
        payload.setdefault("deretraction_speed_mm_s", 30)
        payload.setdefault("wipe_distance_mm", 1.0)
        payload.setdefault("z_hop_mm", 0.2)
        payload.setdefault("pressure_advance", 0.04)
    else:
        payload.setdefault("retraction_length_mm", 0.8)
        payload.setdefault("retraction_speed_mm_s", 35)
        payload.setdefault("deretraction_speed_mm_s", 35)
        payload.setdefault("wipe_distance_mm", 1.0)
        payload.setdefault("z_hop_mm", 0.2)
        payload.setdefault("pressure_advance", 0.025 if not _is_high_temp(material) else 0.04)
    payload.setdefault("drying_temperature_c", dry_temp)
    payload.setdefault("drying_time_hours", dry_hours)
    payload.setdefault("target_printer", "Bambu Lab A1")
    payload.setdefault("printer_vendor", "Bambu Lab")
    payload.setdefault("printer_model", "A1")
    payload.setdefault("a1_specific", True)
    payload["bambu_a1_compatibility"] = compatibility
    payload["native_profile_name"] = native_name
    if native_name:
        payload["inherits"] = native_name
    payload["slicing_supported"] = compatibility != "unsupported_temperature_limits" and bool(native_name)
    payload.setdefault("ams_lite_compatible", not _is_flexible(material) and not _is_support(material))
    payload.setdefault("first_layer_speed_mm_s", 25 if _is_petg(material) else 30)
    payload.setdefault("bridge_fan_percent", min(100, int(payload.get("cooling_fan_max_percent", 100))))
    payload.setdefault("overhang_fan_percent", min(100, int(payload.get("cooling_fan_max_percent", 100))))
    payload.setdefault("slow_down_for_layer_cooling", True)
    payload.setdefault("minimum_layer_time_s", 8 if _is_flexible(material) else 6)
    payload.setdefault("cloud_sync_protected", True)
    payload.setdefault("profile_completeness", "validated_complete")
    return result


def enrich_static_profiles(profiles: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    enriched = tuple(enrich_filament_profile(profile) for profile in profiles)
    validate_complete_profiles(enriched)
    return enriched


def validate_complete_profiles(profiles: Iterable[dict[str, Any]]) -> None:
    failures: list[str] = []
    seen: set[str] = set()
    for profile in profiles:
        profile_id = str(profile.get("id", ""))
        if not profile_id:
            failures.append("profile without id")
            continue
        if profile_id in seen:
            failures.append(f"duplicate id: {profile_id}")
        seen.add(profile_id)
        if profile.get("kind") != "filament" or profile.get("source") != "local":
            continue
        payload = profile.get("payload")
        if not isinstance(payload, dict):
            failures.append(f"{profile_id}: payload missing")
            continue
        missing = sorted(REQUIRED_FILAMENT_FIELDS - set(payload))
        if missing:
            failures.append(f"{profile_id}: missing {', '.join(missing)}")
        nozzle = payload.get("nozzle_temperature_c")
        if not isinstance(nozzle, list) or len(nozzle) != 2 or float(nozzle[0]) > float(nozzle[1]):
            failures.append(f"{profile_id}: invalid nozzle temperature range")
        fan_min = float(payload.get("cooling_fan_min_percent", -1))
        fan_max = float(payload.get("cooling_fan_max_percent", -1))
        if not (0 <= fan_min <= fan_max <= 100):
            failures.append(f"{profile_id}: invalid fan range")
        if float(payload.get("max_volumetric_speed_mm3_s", 0)) <= 0:
            failures.append(f"{profile_id}: invalid volumetric speed")
        if payload.get("slicing_supported") and not str(payload.get("native_profile_name", "")):
            failures.append(f"{profile_id}: supported profile has no native A1 base")
    if failures:
        raise ValueError("Incomplete manufacturer profiles: " + "; ".join(failures))
