"""Resolve the selected Studio build plate to Bambu Studio options."""
from __future__ import annotations

import math
from typing import Any

BED_TYPE_BY_SURFACE: dict[str, str] = {
    "textured_pei": "Textured PEI Plate",
    "smooth_pei": "High Temp Plate",
    "high_temp_plate": "High Temp Plate",
    "cool_plate": "Cool Plate",
    "engineering_plate": "Engineering Plate",
    "cool_plate_super_tack": "Supertack Plate",
    "smooth_cool_plate": "Cool Plate",
    "textured_cool_plate": "Cool Plate",
}


def selected_build_plate_options(catalog: dict[str, Any]) -> dict[str, object]:
    selection = catalog.get("selection")
    if not isinstance(selection, dict):
        raise ValueError("Die Profilwahl enthält keine Druckplattenauswahl.")
    profile_id = str(selection.get("build_plate_profile_id") or "").strip()
    profiles = catalog.get("profiles")
    profile = next(
        (
            item for item in profiles
            if isinstance(item, dict) and str(item.get("id") or "") == profile_id
        ),
        None,
    ) if isinstance(profiles, list) else None
    if not isinstance(profile, dict) or profile.get("kind") != "build_plate":
        raise ValueError("Das gewählte Druckplattenprofil ist nicht verfügbar.")
    payload = profile.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Das gewählte Druckplattenprofil besitzt keine Nutzdaten.")
    surface = str(
        payload.get("surface") or payload.get("plate_type") or payload.get("type") or ""
    ).strip().casefold()
    bed_type = BED_TYPE_BY_SURFACE.get(surface)
    if not bed_type:
        raise ValueError(f"Der Druckplattentyp {surface or profile.get('name')} wird nicht unterstützt.")
    width = float(payload.get("width_mm", 256))
    depth = float(payload.get("depth_mm", 256))
    if isinstance(payload.get("width_mm"), bool) or isinstance(payload.get("depth_mm"), bool) or not math.isfinite(width) or not math.isfinite(depth) or width <= 0 or depth <= 0:
        raise ValueError("Die Druckplattenabmessungen müssen endlich und größer als null sein.")
    return {
        "build_plate_profile_id": profile_id,
        "build_plate_profile_name": str(profile.get("name") or profile_id),
        "build_plate_surface": surface,
        "bambu_bed_type": bed_type,
        "build_plate_width_mm": width,
        "build_plate_depth_mm": depth,
    }
