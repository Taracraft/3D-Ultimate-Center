"""V6 plate slicing with an authoritative AMS or external-spool source."""
from __future__ import annotations

import json
import math
import re
from urllib.parse import unquote

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .bambu_project_archive import safe_project_name
from .build_plate_contract import selected_build_plate_options
from .direct_print_slot_views import _runtimes
from .profile_runtime import get_profile_runtime
from .slicer_backend_router import V6SlicerBackendRouter, normalize_backend
from .slicer_plate_views import API_PREFIX, SlicerModelInspectView, SlicerModelPreviewView, _read_model, _server_error
from .slicer_native_contract import SlicerServerConfigurationError, SlicerServerError
from .process_profile_contract import resolve_selected_process_contract
from .slicer_compatibility_contract import (
    printer_profile_with_validated_limits,
    validate_slicer_compatibility,
)
from .slicer_nozzle_profiles import (
    contract_payload,
    resolve_a1_nozzle_contract,
    validate_process_overrides,
)
from .three_mf_inspector import inspect_model
from .three_mf_mesh_graph import logical_mesh_objects

_GENERIC_PROJECT_NAME = re.compile(
    r"^(?:projekt|project|druckplatte|plate|build[ _-]*plate|druckauftrag|print[ _-]*job)[ _-]*\d*$",
    re.IGNORECASE,
)


def _float_query(request: web.Request, name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(request.query.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} is out of range")
    return value


def _optional_float_query(
    request: web.Request,
    name: str,
    minimum: float,
    maximum: float,
) -> float | None:
    raw = request.query.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} is out of range")
    return value


def _layer_height_ranges_query(request: web.Request) -> list[dict[str, object]] | None:
    raw = request.query.get("layer_height_ranges")
    if raw is None or not raw.strip():
        return None
    if len(raw) > 4096:
        raise ValueError("layer_height_ranges is too large")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("layer_height_ranges must be valid JSON") from exc
    if not isinstance(parsed, list):
        raise ValueError("layer_height_ranges must be an array")
    ranges: list[dict[str, object]] = []
    for index, item in enumerate(parsed, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"layer_height_ranges[{index}] must be an object")
        ranges.append(dict(item))
    return ranges


_PROCESS_OVERRIDE_QUERY_RULES: dict[str, tuple[float, float | None, bool]] = {
    "layer_height_mm": (.04, .56, False),
    "first_layer_height_mm": (.04, .56, False),
    "walls": (0, None, True),
    "top_shell_layers": (0, None, True),
    "bottom_shell_layers": (0, None, True),
    "infill_percent": (0, 100, False),
    "outer_wall_speed_mm_s": (1, 500, False),
    "inner_wall_speed_mm_s": (1, 500, False),
    "travel_speed_mm_s": (1, 500, False),
    "line_width_mm": (.01, None, False),
    "outer_wall_line_width_mm": (.01, None, False),
    "inner_wall_line_width_mm": (.01, None, False),
    "top_surface_line_width_mm": (.01, None, False),
    "support_line_width_mm": (.01, None, False),
    "sparse_infill_speed_mm_s": (1, None, False),
    "internal_solid_infill_speed_mm_s": (1, None, False),
    "top_surface_speed_mm_s": (1, None, False),
    "initial_layer_speed_mm_s": (1, None, False),
    "bridge_speed_mm_s": (1, None, False),
    "gap_infill_speed_mm_s": (1, None, False),
    "solid_infill_speed_mm_s": (1, None, False),
    "ironing_speed_mm_s": (1, None, False),
    "support_speed_mm_s": (1, None, False),
    "support_interface_speed_mm_s": (1, None, False),
    "bridge_flow_ratio": (0, None, False),
    "support_top_z_distance_mm": (0, None, False),
    "support_bottom_z_distance_mm": (0, None, False),
    "support_object_xy_distance_mm": (0, None, False),
    "support_interface_spacing_mm": (0, None, False),
    "support_interface_top_layers": (0, None, True),
    "support_interface_bottom_layers": (0, None, True),
}


def _process_override_query(request: web.Request, name: str, minimum: float, maximum: float | None, integer: bool) -> float | int | None:
    raw = request.query.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is out of range")
    if integer:
        if not value.is_integer():
            raise ValueError(f"{name} must be an integer")
        return int(value)
    return value


def _options(request: web.Request) -> dict[str, object]:
    adhesion = request.query.get("adhesion_mode", "none").casefold()
    support = request.query.get("support_mode", "off").casefold()
    support_style = request.query.get("support_style", "standard").casefold()
    if adhesion not in {"none", "brim", "raft"}:
        raise ValueError("adhesion_mode is invalid")
    if support not in {"off", "normal", "tree"}:
        raise ValueError("support_mode is invalid")
    if support_style not in {"standard", "tree_slim", "tree_strong", "tree_hybrid", "tree_organic"}:
        raise ValueError("support_style is invalid")
    options: dict[str, object] = {
        "adhesion_mode": adhesion,
        "support_mode": support,
        "support_style": support_style,
    }
    if adhesion == "brim":
        options["brim_width_mm"] = _float_query(request, "brim_width_mm", 5, 1, 30)
    elif adhesion == "raft":
        options["raft_layers"] = int(round(_float_query(request, "raft_layers", 2, 1, 10)))
    if support != "off":
        plate_only = request.query.get("support_build_plate_only", "true").casefold()
        if plate_only not in {"true", "false"}:
            raise ValueError("support_build_plate_only is invalid")
        options["support_build_plate_only"] = plate_only == "true"
        options["support_threshold_angle"] = int(round(_float_query(request, "support_threshold_angle", 30, 0, 89)))
    layer_height = _optional_float_query(request, "layer_height_mm", .04, .56)
    outer_speed = _optional_float_query(request, "outer_wall_speed_mm_s", 1, 500)
    inner_speed = _optional_float_query(request, "inner_wall_speed_mm_s", 1, 500)
    layer_height_ranges = _layer_height_ranges_query(request)
    if layer_height is not None:
        options["layer_height_mm"] = layer_height
    if outer_speed is not None:
        options["outer_wall_speed_mm_s"] = outer_speed
    if inner_speed is not None:
        options["inner_wall_speed_mm_s"] = inner_speed
    for key, (minimum, maximum, integer) in _PROCESS_OVERRIDE_QUERY_RULES.items():
        value = _process_override_query(request, key, minimum, maximum, integer)
        if value is not None:
            options[key] = value
    if layer_height_ranges is not None:
        options["layer_height_ranges"] = layer_height_ranges
    return options


def _header_json(request: web.Request, name: str, label: str) -> dict[str, object] | None:
    raw = request.headers.get(name, "").strip()
    if not raw:
        return None
    if len(raw) > 1_000_000:
        raise ValueError(f"{label} header is too large")
    try:
        decoded = json.loads(unquote(raw))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must be an object")
    return decoded


def _material_plan(request: web.Request) -> dict[str, object] | None:
    decoded = _header_json(request, "X-U3D-Material-Plan", "material plan")
    if decoded is None:
        return None
    if decoded.get("assignments") is not None and not isinstance(decoded.get("assignments"), dict):
        raise ValueError("material plan assignments must be an object")
    if decoded.get("filaments") is not None and not isinstance(decoded.get("filaments"), list):
        raise ValueError("material plan filaments must be an array")
    if decoded.get("purge_tower") is not None and not isinstance(decoded.get("purge_tower"), dict):
        raise ValueError("material plan purge_tower must be an object")
    return decoded


def _studio_plate(request: web.Request) -> dict[str, object] | None:
    return _header_json(request, "X-U3D-Studio-Plate", "studio plate")


def _studio_project_name(
    studio_plate: dict[str, object] | None,
    fallback: str,
) -> str | None:
    """Return a real source project name and reject plate placeholders."""
    plate = studio_plate or {}
    for value in (plate.get("project_name"), fallback):
        raw = str(value or "").strip()
        if not raw:
            continue
        name = safe_project_name(raw, "Druckauftrag")
        if name and not _GENERIC_PROJECT_NAME.fullmatch(name):
            return name
    return None


def canonical_model(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    for names, key in (
        (("a1 mini", "a1m"), "a1_mini"), (("x1 carbon", "x1c"), "x1c"),
        (("x1e",), "x1e"), (("p1s",), "p1s"), (("p1p",), "p1p"),
        (("a1",), "a1"), (("x1",), "x1"),
    ):
        if any(name in text for name in names):
            return key
    return text.replace(" ", "_") or "unknown"


def _profile_model(profile: dict[str, object]) -> str:
    payload = profile.get("payload") if isinstance(profile.get("payload"), dict) else {}
    return canonical_model(payload.get("model") or profile.get("name"))


def _printer_model(printer) -> str:
    return canonical_model(" ".join(filter(None, (printer.model, printer.name))))


def _catalog_for_plate(catalog: dict[str, object], studio_plate: dict[str, object] | None) -> dict[str, object]:
    result = dict(catalog)
    selection = dict(catalog.get("selection", {}))
    plate = studio_plate or {}
    for key in ("printer_profile_id", "nozzle_profile_id", "process_profile_id", "build_plate_profile_id"):
        if plate.get(key):
            selection[key] = plate[key]
    if isinstance(plate.get("filament_profile_ids"), list):
        selection["filament_profile_ids"] = [str(item) for item in plate["filament_profile_ids"]]
    result["selection"] = selection
    return result


async def _resolve_target(hass: HomeAssistant, studio_plate: dict[str, object] | None, catalog: dict[str, object]):
    target_id = str((studio_plate or {}).get("target_printer_id") or "").strip()
    if not target_id:
        raise ValueError("Vor dem Slicing muss ein Ziel-Drucker gewählt werden.")
    printers = []
    for runtime in _runtimes(hass):
        printers.extend(await runtime.async_printers())
    printer = next((item for item in printers if item.printer_id == target_id), None)
    if printer is None:
        raise ValueError("Der gewählte Ziel-Drucker ist nicht mehr verfügbar.")
    selection = catalog.get("selection", {})
    profile_id = str(selection.get("printer_profile_id") or "") if isinstance(selection, dict) else ""
    profiles = catalog.get("profiles", [])
    profile = next((item for item in profiles if isinstance(item, dict) and str(item.get("id", "")) == profile_id), None) if isinstance(profiles, list) else None
    if not isinstance(profile, dict):
        raise ValueError("Das gewählte Druckerprofil ist nicht verfügbar.")
    if _profile_model(profile) != _printer_model(printer):
        raise ValueError("Das gewählte Druckerprofil passt nicht zum Ziel-Drucker.")
    return printer, printer_profile_with_validated_limits(catalog, profile)


def _normal_color(value: object) -> str:
    raw = str(value or "").strip().removeprefix("#").upper()
    if len(raw) >= 6 and re.fullmatch(r"[0-9A-F]{6,8}", raw):
        return f"#{raw[:6]}"
    return ""


def _mesh_objects(model: bytes) -> list[tuple[str, str]]:
    return logical_mesh_objects(model)


def _ordered_object_assignments(
    model: bytes,
    assignments: dict[str, object],
    filaments: list[object],
) -> dict[str, int]:
    objects = _mesh_objects(model)
    if not objects:
        raise ValueError("Die 3MF enthält keine Meshobjekte.")
    if len(assignments) == len(objects):
        object_ids = [item[0] for item in objects]
        if set(assignments) == set(object_ids):
            return {object_id: int(assignments[object_id]) for object_id in object_ids}
        return dict(zip(object_ids, (int(value) for value in assignments.values()), strict=True))

    used = {int(value) for value in assignments.values() if int(value) > 0}
    by_color: dict[str, list[int]] = {}
    for index, item in enumerate(filaments, start=1):
        if index not in used or not isinstance(item, dict):
            continue
        color = _normal_color(item.get("color"))
        if color:
            by_color.setdefault(color, []).append(index)
    resolved: dict[str, int] = {}
    for object_id, color in objects:
        candidates = by_color.get(color, [])
        if len(candidates) != 1:
            raise ValueError(
                "Die aktive Platte kann nicht eindeutig aus den globalen Materialzuweisungen abgeleitet werden. "
                "Bitte jeden Teil dieser Platte einem eindeutig gefärbten AMS-Slot zuweisen."
            )
        resolved[object_id] = candidates[0]
    return resolved


def _slot_dicts(printer) -> list[dict[str, object]]:
    ams = printer.ams if isinstance(printer.ams, dict) else {}
    return [item for item in ams.get("slots", []) if isinstance(item, dict) and bool(item.get("present"))]


def _resolve_ams_plan(plan: dict[str, object] | None, printer, model: bytes) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(plan, dict):
        raise ValueError("Vor dem Slicing muss eine Materialquelle gewählt werden.")
    raw_assignments = plan.get("assignments")
    filaments = plan.get("filaments")
    if not isinstance(raw_assignments, dict) or not isinstance(filaments, list):
        raise ValueError("Der Materialplan ist unvollständig.")
    assignments = _ordered_object_assignments(model, raw_assignments, filaments)
    source = str(plan.get("source") or "ams").strip().casefold()
    if source == "external_spool":
        if len(filaments) != 1 or not isinstance(filaments[0], dict):
            raise ValueError("Die externe Spule benötigt genau ein Filamentprofil.")
        if not assignments or any(value != 1 for value in assignments.values()):
            raise ValueError("Die externe Spule unterstützt genau einen Materialkanal für alle Objekte.")
        requested = filaments[0]
        material = str(requested.get("material") or "").strip()
        color = _normal_color(requested.get("color"))
        filament_id = str(requested.get("filament_id") or "").strip()
        name = str(requested.get("name") or "").strip()
        if not name or not material or not color or not filament_id:
            raise ValueError("Das Filamentprofil der externen Spule ist unvollständig.")
        resolved_filament = {
            "extruder": 1,
            "name": name,
            "material": material,
            "color": color,
            "filament_id": filament_id,
            "source": "external_spool",
        }
        purge = dict(plan.get("purge_tower") or {})
        purge["enabled"] = False
        resolved = {
            "assignments": {object_id: 1 for object_id in assignments},
            "filaments": [resolved_filament],
            "purge_tower": purge,
            "source": "authoritative_external_spool_runtime",
            "target_printer_id": printer.printer_id,
        }
        return resolved, {
            "source": "authoritative_external_spool_runtime",
            "target_printer_id": printer.printer_id,
            "use_ams": False,
            "physical_extruder_count": 1,
            "material_channel_count": 1,
            "filaments": [resolved_filament],
            "purge_tower": purge,
        }
    if source != "ams":
        raise ValueError("Die gewählte Materialquelle ist ungültig.")
    slots = _slot_dicts(printer)
    if not slots:
        raise ValueError("Am Ziel-Drucker ist kein belegter AMS-Slot verfügbar.")
    used = sorted({value for value in assignments.values() if value > 0})
    remap: dict[int, int] = {}
    resolved_filaments: list[dict[str, object]] = []
    for old_index in used:
        if old_index > len(filaments) or not isinstance(filaments[old_index - 1], dict):
            raise ValueError(f"Materialreferenz {old_index} ist ungültig.")
        requested = filaments[old_index - 1]
        requested_global_id = str(requested.get("global_id") or "").strip()
        if requested_global_id:
            candidates = [item for item in slots if str(item.get("global_id") or "") == requested_global_id]
        else:
            match = re.match(r"^AMS\s+(\d+)\s*:", str(requested.get("name") or ""), re.IGNORECASE)
            display_slot = int(match.group(1)) if match else -1
            candidates = [item for item in slots if int(item.get("slot_index", -1)) + 1 == display_slot]
        if len(candidates) != 1:
            raise ValueError(f"Material {old_index} ist keinem eindeutigen AMS-Slot des Ziel-Druckers zugeordnet.")
        slot = candidates[0]
        display_slot = int(slot.get("slot_index", 0)) + 1
        if not slot.get("color") or not slot.get("material"):
            raise ValueError(f"AMS-Slot {display_slot} enthält keine vollständigen Materialdaten.")
        compact_index = len(resolved_filaments) + 1
        remap[old_index] = compact_index
        resolved_filaments.append({
            "extruder": compact_index,
            "name": f"AMS {display_slot}: {slot.get('sub_brand') or slot.get('material') or 'Filament'}",
            "material": str(slot.get("material") or ""),
            "color": str(slot.get("color") or ""),
            "global_id": str(slot.get("global_id") or ""),
            "unit_id": str(slot.get("unit_id") or ""),
            "slot_index": int(slot.get("slot_index", 0) or 0),
            "display_slot": display_slot,
            "tray_id": str(slot.get("tray_id") or ""),
            "filament_id": str(slot.get("filament_id") or slot.get("tray_id") or ""),
            "diameter": slot.get("diameter"),
            "nozzle_temp_min": slot.get("nozzle_temp_min"),
            "nozzle_temp_max": slot.get("nozzle_temp_max"),
            "bed_temp": slot.get("bed_temp"),
            "rfid_detected": bool(slot.get("rfid_detected")),
        })
    resolved_assignments = {object_id: remap[value] for object_id, value in assignments.items() if value in remap}
    if len(resolved_assignments) != len(assignments):
        raise ValueError("Mindestens ein Objekt besitzt keine gültige AMS-Zuordnung.")
    purge = dict(plan.get("purge_tower") or {})
    purge["enabled"] = len(resolved_filaments) > 1 and purge.get("enabled") is not False
    resolved = {
        "assignments": resolved_assignments,
        "filaments": resolved_filaments,
        "purge_tower": purge,
        "source": "authoritative_ams_runtime",
        "target_printer_id": printer.printer_id,
    }
    return resolved, {
        "source": "authoritative_ams_runtime",
        "target_printer_id": printer.printer_id,
        "use_ams": True,
        "physical_extruder_count": 1,
        "material_channel_count": len(resolved_filaments),
        "filaments": resolved_filaments,
        "purge_tower": purge,
    }


def _batch_material_plan_for_model(
    plan: dict[str, object] | None,
    model: bytes,
) -> dict[str, object]:
    """Map batch model objects only to explicitly selected, color-matched channels."""
    if not isinstance(plan, dict):
        raise ValueError("Für den Batch fehlt eine ausdrücklich gewählte Materialquelle.")
    filaments = plan.get("filaments")
    assignments = plan.get("assignments")
    if not isinstance(filaments, list) or not filaments or not isinstance(assignments, dict):
        raise ValueError("Der Materialplan ist unvollständig.")
    objects = _mesh_objects(model)
    if not objects:
        raise ValueError("Die 3MF enthält keine zuordenbaren Meshobjekte.")
    source = str(plan.get("source") or "ams").strip().casefold()
    if source == "external_spool":
        if len(filaments) != 1 or not isinstance(filaments[0], dict):
            raise ValueError("Die externe Spule benötigt genau ein gewähltes Filamentprofil.")
        return {**plan, "assignments": {object_id: 1 for object_id, _ in objects}}
    if source != "ams":
        raise ValueError("Die gewählte Batch-Materialquelle ist ungültig.")
    used = {int(value) for value in assignments.values() if int(value) > 0}
    by_color: dict[str, list[int]] = {}
    for index, filament in enumerate(filaments, start=1):
        if index not in used or not isinstance(filament, dict):
            continue
        color = _normal_color(filament.get("color"))
        if color:
            by_color.setdefault(color, []).append(index)
    mapped: dict[str, int] = {}
    for object_id, color in objects:
        candidates = by_color.get(_normal_color(color), [])
        if len(candidates) != 1:
            raise ValueError(
                "Die Batch-Datei kann nicht eindeutig den ausdrücklich ausgewählten AMS-Filamentprofilen "
                "zugeordnet werden. Gleiche Farben oder fehlende Profile müssen im Studio geklärt werden."
            )
        mapped[object_id] = candidates[0]
    return {**plan, "assignments": mapped}


async def _prepare_plate_job_contract(
    hass: HomeAssistant,
    filename: str,
    model: bytes,
    plate_index: int,
    options: dict[str, object],
    material_plan: dict[str, object] | None,
    studio_plate: dict[str, object] | None,
) -> dict[str, object]:
    """Resolve the same validated slicing contract for single and batch jobs."""
    inspection = await hass.async_add_executor_job(inspect_model, filename, model)
    valid_indexes = {
        int(item.get("plate_index", -1))
        for item in inspection.get("plates", [])
        if isinstance(item, dict)
    }
    if plate_index not in valid_indexes:
        raise ValueError(
            f"Druckplatte {plate_index + 1} ist in dieser Datei nicht vorhanden"
        )

    catalog = _catalog_for_plate(
        await get_profile_runtime(hass).async_catalog(),
        studio_plate,
    )
    build_plate_options = selected_build_plate_options(catalog)
    resolved_options = dict(options)
    resolved_options.update(build_plate_options)
    target_printer, target_profile = await _resolve_target(
        hass,
        studio_plate,
        catalog,
    )
    nozzle_contract = resolve_a1_nozzle_contract(catalog, {
        "name": target_printer.name,
        "model": target_printer.model,
    })
    selected_process_profile = resolve_selected_process_contract(
        catalog,
        nozzle_contract,
    )
    resolved_options = validate_process_overrides(
        resolved_options,
        nozzle_contract,
    )
    resolved_plan, material_source_summary = _resolve_ams_plan(
        material_plan,
        target_printer,
        model,
    )
    resolved_plan, compatibility_contract = validate_slicer_compatibility(
        catalog,
        nozzle_contract,
        resolved_plan,
        build_plate_options,
        target_profile,
    )
    payload = target_profile.get("payload") if isinstance(target_profile.get("payload"), dict) else {}
    target_context = {
        "printer_id": target_printer.printer_id,
        "name": target_printer.name,
        "model": target_printer.model,
        "serial": target_printer.serial,
        "profile_id": target_profile.get("id"),
        "physical_extruder_count": int(payload.get("physical_extruder_count", 1)),
        "material_channel_system": (
            "ams_single_nozzle"
            if bool(material_source_summary.get("use_ams"))
            else "external_spool_single_nozzle"
        ),
        **contract_payload(nozzle_contract),
    }
    return {
        "catalog": catalog,
        "options": resolved_options,
        "target_printer": target_context,
        "material_plan": resolved_plan,
        "material_source_summary": material_source_summary,
        "compatibility_contract": compatibility_contract,
        "selected_process_profile": selected_process_profile,
        "project_name": _studio_project_name(studio_plate, filename),
    }


class SlicerPlateJobViewV2(HomeAssistantView):
    url = f"{API_PREFIX}/jobs-plate"
    name = "api:ultimate_3d_studio_v6:slicer_plate_job_v2"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        loaded = await _read_model(request)
        if isinstance(loaded, web.Response):
            return loaded
        filename, model = loaded
        try:
            plate_index = int(request.query.get("plate_index", "0"))
            backend = normalize_backend(request.query.get("backend", "server"))
            options = _options(request)
            material_plan = _material_plan(request)
            studio_plate = _studio_plate(request)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        if plate_index < 0 or plate_index > 255:
            return web.json_response({"error": "plate_index is out of range"}, status=400)

        hass: HomeAssistant = request.app["hass"]
        try:
            contract = await _prepare_plate_job_contract(
                hass,
                filename,
                model,
                plate_index,
                options,
                material_plan,
                studio_plate,
            )
            job = await V6SlicerBackendRouter(hass).async_create_plate_job(
                backend,
                filename,
                model,
                contract["catalog"],
                plate_index,
                contract["options"],
                target_printer=contract["target_printer"],
                material_plan=contract["material_plan"],
                selected_process_profile=contract["selected_process_profile"],
                source_project_name=contract["project_name"],
            )
            resolved_plan = contract["material_plan"]
            material_summary = contract["material_source_summary"]
            compatibility_contract = contract["compatibility_contract"]
            job["material_plan"] = {
                "applied": False,
                "handled_by_native_server": True,
                "assignment_count": len(resolved_plan["assignments"]),
                "material_channel_count": len(resolved_plan["filaments"]),
            }
            job["material_source_plan"] = material_summary
            job["compatibility_contract"] = compatibility_contract
            if bool(material_summary.get("use_ams")):
                job["ams_material_plan"] = material_summary
            job["target_printer"] = contract["target_printer"]
            job["selected_backend"] = backend
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except (SlicerServerConfigurationError, SlicerServerError) as exc:
            return _server_error(exc)
        return web.json_response({"data": job}, status=202)


def async_register_slicer_plate_views_v2(hass: HomeAssistant) -> None:
    for view in (SlicerModelInspectView(), SlicerModelPreviewView(), SlicerPlateJobViewV2()):
        hass.http.register_view(view)
