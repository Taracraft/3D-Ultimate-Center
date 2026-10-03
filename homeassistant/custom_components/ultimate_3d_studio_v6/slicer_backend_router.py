"""Native Linux slicer routing for Ultimate 3D Studio V6."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any
from uuid import uuid4
import re

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bambu_project_archive import (
    gcode_from_bambu_project_artifact,
    prepare_bambu_project_artifact,
    project_name_from_3mf,
    project_name_from_server_payload,
    safe_project_name,
)
from .filament_profile_mapping import attach_selected_profiles
from .gcode_analysis import analyze_gcode, assert_prime_tower_inside, extract_gcode_settings, extract_heater_commands
from .slicer_native_contract import (
    SlicerServerConfigurationError,
    SlicerServerError,
)
from .filament_parameter_contract import ALIASES, BED_TEMPERATURE_KEYS
from .slicer_execution_contract import bind_execution_contract, job_hardware_limits
from .slicer_nozzle_profiles import (
    contract_payload,
    resolve_nozzle_contract,
    validate_process_overrides,
)

BACKEND_SERVER = "server"
SERVER_ENDPOINT = "http://127.0.0.1:8099"
SERVER_PREFIX = "server__"
SERVER_PRINTER_PROFILES = {
    "a1": "bambu_lab_a1_04",
    "h2s": "bambu_lab_h2s_04",
}
_COMPLETED_ARTIFACT_CACHE: OrderedDict[
    str,
    tuple[bytes, str, str, dict[str, Any]],
] = OrderedDict()
_MAX_COMPLETED_ARTIFACT_CACHE = 1
_COMPLETED_METADATA_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_MAX_COMPLETED_METADATA_CACHE = 100


def normalize_backend(value: object = BACKEND_SERVER) -> str:
    """Accept only the native Linux slicing server."""
    requested = str(value or BACKEND_SERVER).strip().casefold()
    if requested != BACKEND_SERVER:
        raise ValueError(
            "Nur der native Linux-Slicing-Server ist zulässig."
        )
    return BACKEND_SERVER


def native_job_id(job_id: str) -> str:
    """Validate and unwrap a native server job identifier."""
    requested = str(job_id or "").strip()
    if not requested.startswith(SERVER_PREFIX):
        raise SlicerServerError(
            "Ungültige Slicerauftrag-ID: server__-Präfix erforderlich."
        )
    raw_id = requested[len(SERVER_PREFIX):]
    if not raw_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}", raw_id):
        raise SlicerServerError("Ungültige native Slicerauftrag-ID.")
    return raw_id


def _canonical_model(value: object) -> str:
    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").casefold(),
    ).strip()
    for names, key in (
        (("h2s",), "h2s"),
        (("a1 mini", "a1m"), "a1_mini"),
        (("x1 carbon", "x1c"), "x1c"),
        (("x1e",), "x1e"),
        (("p1s",), "p1s"),
        (("p1p",), "p1p"),
        (("a1",), "a1"),
        (("x1",), "x1"),
    ):
        if any(name in text for name in names):
            return key
    return text.replace(" ", "_") or "unknown"


def _server_printer_profile(
    target_printer: dict[str, Any] | None,
) -> str:
    target = target_printer or {}
    model = _canonical_model(target.get("model") or target.get("name"))
    profile = SERVER_PRINTER_PROFILES.get(model)
    if not profile:
        raise SlicerServerConfigurationError(
            f"Für das Druckermodell "
            f"{target.get('model') or target.get('name') or model} "
            "ist auf dem nativen Server noch kein validiertes Profil installiert."
        )
    return profile



def _gcode_metadata(
    data: bytes,
    selected_setting_keys: list[str] | None = None,
    limits: dict[str, float] | None = None,
    printer_model: str | None = None,
) -> dict[str, Any]:
    analysis = analyze_gcode(data, plate_width_mm=limits["width_mm"], plate_depth_mm=limits["depth_mm"]) if limits else analyze_gcode(data)
    assert_prime_tower_inside(analysis)
    totals = (
        analysis.get("totals")
        if isinstance(analysis.get("totals"), dict)
        else {}
    )
    time = (
        analysis.get("time")
        if isinstance(analysis.get("time"), dict)
        else {}
    )
    materials = (
        analysis.get("materials")
        if isinstance(analysis.get("materials"), list)
        else []
    )
    return {
        "print_time_seconds": time.get("total_seconds"),
        "model_time_seconds": time.get("model_seconds"),
        "preparation_time_seconds": time.get("preparation_seconds"),
        "filament_used_g": totals.get("weight_g"),
        "filament_length_mm": totals.get("length_mm"),
        "filament_volume_cm3": totals.get("volume_cm3"),
        "layer_count": analysis.get("layer_count"),
        "filament_change_count": analysis.get("filament_change_count"),
        "material_channel_count": analysis.get("material_channel_count"),
        "analysis": analysis,
        "gcode_profile_settings": extract_gcode_settings(
            data,
            set(selected_setting_keys or []) | set(ALIASES.values())
            | {"nozzle_temperature", "nozzle_temperature_initial_layer", "nozzle_temperature_range_low", "nozzle_temperature_range_high", "slow_down_for_layer_cooling"}
            | {key + suffix for key in BED_TEMPERATURE_KEYS.values() for suffix in ("", "_initial_layer")},
        ),
        "heater_commands": extract_heater_commands(data, printer_model=printer_model),
        "consumption": {
            "physical_extruder_count": analysis.get(
                "physical_extruder_count",
            ),
            "material_channel_count": analysis.get(
                "material_channel_count",
            ),
            "filament_change_count": analysis.get(
                "filament_change_count",
            ),
            "channels": materials,
            "totals": totals,
            "estimated": analysis.get("estimated_material_values"),
        },
    }


def _effective_numeric_process_settings(
    settings: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Apply the three validated numeric job overrides to expected settings."""
    effective = dict(settings)
    for override_key, native_key in (
        ("layer_height_mm", "layer_height"),
        ("outer_wall_speed_mm_s", "outer_wall_speed"),
        ("inner_wall_speed_mm_s", "inner_wall_speed"),
    ):
        value = overrides.get(override_key)
        if value is not None:
            effective[native_key] = value
    return effective


def _prepare_server_artifact(
    job_id: str,
    payload: dict[str, Any],
    data: bytes,
) -> tuple[bytes, str, str, dict[str, Any]]:
    gcode = gcode_from_bambu_project_artifact(data)
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    process_overrides = (
        job.get("process_overrides")
        if isinstance(job.get("process_overrides"), dict)
        else {}
    )
    selected_process = (
        process_overrides.get("selected_process_profile")
        if isinstance(process_overrides.get("selected_process_profile"), dict)
        else {}
    )
    selected_settings = (
        selected_process.get("settings")
        if isinstance(selected_process.get("settings"), dict)
        else {}
    )
    effective_settings = _effective_numeric_process_settings(
        selected_settings, process_overrides,
    )
    metadata = _gcode_metadata(gcode, list(effective_settings), job_hardware_limits(job), (job.get("target_printer") or {}).get("model"))
    project_name = project_name_from_server_payload(
        payload,
        job_id,
        gcode,
    )
    content, filename, digest = prepare_bambu_project_artifact(
        project_name,
        data,
        job_id,
    )
    return content, filename, digest, metadata


def _cached_artifact(
    raw_id: str,
) -> tuple[bytes, str, str, dict[str, Any]] | None:
    result = _COMPLETED_ARTIFACT_CACHE.get(raw_id)
    if result is not None:
        _COMPLETED_ARTIFACT_CACHE.move_to_end(raw_id)
    return result


def _cached_metadata(raw_id: str) -> dict[str, Any] | None:
    result = _COMPLETED_METADATA_CACHE.get(raw_id)
    if result is not None:
        _COMPLETED_METADATA_CACHE.move_to_end(raw_id)
    return result


def _store_artifact(
    raw_id: str,
    result: tuple[bytes, str, str, dict[str, Any]],
) -> None:
    _COMPLETED_ARTIFACT_CACHE[raw_id] = result
    _COMPLETED_ARTIFACT_CACHE.move_to_end(raw_id)
    while len(_COMPLETED_ARTIFACT_CACHE) > _MAX_COMPLETED_ARTIFACT_CACHE:
        _COMPLETED_ARTIFACT_CACHE.popitem(last=False)
    _COMPLETED_METADATA_CACHE[raw_id] = result[3]
    _COMPLETED_METADATA_CACHE.move_to_end(raw_id)
    while len(_COMPLETED_METADATA_CACHE) > _MAX_COMPLETED_METADATA_CACHE:
        _COMPLETED_METADATA_CACHE.popitem(last=False)



def _build_detailed_warning(plate, original_warning):
    if not original_warning:
        return None
    
    feature_times = plate.get("feature_type_times", {})
    bridge_seconds = feature_times.get("bridge", 0.0)
    overhang_seconds = feature_times.get("overhang wall", 0.0)
    support_seconds = (
        feature_times.get("support", 0.0) + 
        feature_times.get("support interface", 0.0)
    )
    
    if bridge_seconds <= 0 and overhang_seconds <= 0:
        return original_warning
    
    parts = [original_warning]
    
    if bridge_seconds > 0:
        hours, remainder = divmod(int(bridge_seconds), 3600)
        minutes = remainder // 60
        seconds = remainder % 60
        time_str = f"{hours}h {minutes:02d}m {seconds:02d}s" if hours else f"{minutes}m {seconds:02d}s"
        parts.append(f"Bridge: {time_str}")
    
    if overhang_seconds > 0:
        minutes = int(overhang_seconds) // 60
        seconds = int(overhang_seconds) % 60
        parts.append(f"Overhang: {minutes}m {seconds:02d}s")
    
    objects = plate.get("objects", [])
    floating_objects = []
    
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        obj_name = obj.get("name", "unknown")
        warning_msg = obj.get("warning_message", "") or ""
        
        if "floating" in warning_msg.lower() or "overhang" in warning_msg.lower():
            bbox = obj.get("bbox", {})
            floating_objects.append({
                "name": obj_name,
                "id": obj.get("id"),
                "position": (bbox.get("x", 0), bbox.get("y", 0)),
                "size": (bbox.get("width", 0), bbox.get("depth", 0), bbox.get("height", 0)),
            })
    
    if floating_objects:
        parts.append("\nFloating regions detected:")
        for obj_info in floating_objects:
            x, y = obj_info["position"]
            w, d, h = obj_info["size"]
            parts.append(
                f"  * {obj_info[ name]}: "
                f"Position ({x:.1f}, {y:.1f})mm, "
                f"Size {w:.1f}x{d:.1f}x{h:.1f}mm"
            )
    
    if support_seconds <= 0 and (bridge_seconds > 0 or overhang_seconds > 0):
        parts.append(
            "\nWarning: No support structure enabled. "
            "Enable support generation to prevent print failures."
        )
    
    return "\n".join(parts)


def _engine_result_metrics(engine_result: dict[str, Any], requested_plate_index: int) -> dict[str, Any]:
    def number(value: object) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed == parsed else None

    raw_plates = engine_result.get("sliced_plates")
    plates = raw_plates if isinstance(raw_plates, list) else []
    plate = None
    for candidate in plates:
        if not isinstance(candidate, dict):
            continue
        try:
            candidate_id = int(candidate.get("id") or 0)
        except (TypeError, ValueError):
            candidate_id = 0
        if candidate_id == requested_plate_index + 1:
            plate = candidate
            break
    if plate is None:
        plate = next((item for item in plates if isinstance(item, dict)), {})
    raw_filaments = plate.get("filaments")
    filaments = raw_filaments if isinstance(raw_filaments, list) else []
    filament_used_g = sum(number(item.get("total_used_g")) or 0.0 for item in filaments if isinstance(item, dict))
    total_prediction = number(plate.get("total_predication"))
    model_prediction = number(plate.get("main_predication"))
    preparation = None
    if total_prediction is not None and model_prediction is not None:
        preparation = max(0.0, total_prediction - model_prediction)
    return {
        "return_code": engine_result.get("return_code"),
        "error_string": engine_result.get("error_string"),
        "layer_height_mm": number(engine_result.get("layer_height")),
        "plate_index": engine_result.get("plate_index"),
        "triangle_count": plate.get("triangle_count"),
        "print_time_seconds": total_prediction,
        "model_time_seconds": model_prediction,
        "preparation_time_seconds": preparation,
        "slice_time_ms": plate.get("sliced_time"),
        "filament_used_g": filament_used_g or None,
        "filament_change_count": plate.get("filament_change_times"),
        "original_warning": plate.get("warning_message") or None,
        "warning": _build_detailed_warning(plate, plate.get("warning_message") or None),
    }


def _normalized_setting_values(value: object) -> list[tuple[str, object]]:
    raw = value if isinstance(value, list) else [value]
    result: list[tuple[str, object]] = []
    for item in raw:
        text = str(item).strip().strip('"').removesuffix("%").strip()
        try:
            number = float(text)
        except (TypeError, ValueError):
            result.append(("text", text.casefold()))
        else:
            result.append(("number", round(number, 8)))
    return result


def _settings_confirmed(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> tuple[bool, int]:
    confirmed = 0
    for key, value in expected.items():
        actual_value = actual.get(str(key).casefold())
        if actual_value is None:
            return False, confirmed
        if _normalized_setting_values(value) != _normalized_setting_values(actual_value):
            return False, confirmed
        confirmed += 1
    return bool(expected), confirmed


def _normalized_material(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _normalized_color(value: object) -> str:
    raw = str(value or "").strip().removeprefix("#").upper()
    return raw[:6] if re.fullmatch(r"[0-9A-F]{6,8}", raw) else ""


def _materials_confirmed(
    applied_filaments: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> bool:
    raw = analysis.get("materials")
    actual = raw if isinstance(raw, list) else []
    if len(actual) != len(applied_filaments):
        return False
    for expected, observed in zip(applied_filaments, actual, strict=True):
        if not isinstance(observed, dict):
            return False
        native_type = (expected.get("parameter_settings") or {}).get("filament_type")
        expected_material = native_type[0] if isinstance(native_type, list) and len(native_type) == 1 else expected.get("material")
        if _normalized_material(expected_material) != _normalized_material(
            observed.get("material")
        ):
            return False
        expected_color = _normalized_color(expected.get("color"))
        observed_color = _normalized_color(observed.get("color"))
        if expected_color and expected_color != observed_color:
            return False
        expected_id = str(expected.get("filament_id") or "").strip()
        observed_id = str(observed.get("filament_id") or "").strip()
        if expected_id and observed_id and expected_id != observed_id:
            return False
    return True


def _profile_application(
    job: dict[str, Any],
    runtime: dict[str, Any],
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    material_plan = (
        job.get("material_plan")
        if isinstance(job.get("material_plan"), dict)
        else {}
    )
    process_overrides = (
        job.get("process_overrides")
        if isinstance(job.get("process_overrides"), dict)
        else {}
    )
    selected_process = (
        process_overrides.get("selected_process_profile")
        if isinstance(process_overrides.get("selected_process_profile"), dict)
        else {}
    )
    settings = (
        selected_process.get("settings")
        if isinstance(selected_process.get("settings"), dict)
        else {}
    )
    raw_selected_filaments = material_plan.get("filaments")
    selected_filaments = [
        item for item in raw_selected_filaments
        if isinstance(item, dict)
        and isinstance(item.get("selected_profile"), dict)
    ] if isinstance(raw_selected_filaments, list) else []
    selected = bool(
        selected_process.get("profile_id")
        and selected_process.get("contract_sha256")
        and isinstance(settings, dict)
        and raw_selected_filaments
        and len(selected_filaments) == len(raw_selected_filaments)
    )

    process_proof = (
        runtime.get("selected_process_profile")
        if isinstance(runtime.get("selected_process_profile"), dict)
        else {}
    )
    raw_applied_filaments = runtime.get("filaments")
    applied_filaments = [
        item for item in raw_applied_filaments if isinstance(item, dict)
    ] if isinstance(raw_applied_filaments, list) else []
    process_applied = bool(
        process_proof.get("applied") is True
        and process_proof.get("profile_id") == selected_process.get("profile_id")
        and process_proof.get("contract_sha256")
        == selected_process.get("contract_sha256")
    )
    filament_profiles_applied = (
        len(applied_filaments) == len(selected_filaments)
        and all(
            str(applied.get("selected_profile_id") or "")
            == str(selected_item.get("selected_profile", {}).get("id") or "")
            for selected_item, applied in zip(
                selected_filaments,
                applied_filaments,
                strict=True,
            )
        )
    )
    applied = selected and process_applied and filament_profiles_applied

    meta = metadata if isinstance(metadata, dict) else {}
    actual_settings = (
        meta.get("gcode_profile_settings")
        if isinstance(meta.get("gcode_profile_settings"), dict)
        else {}
    )
    effective_settings = _effective_numeric_process_settings(settings, process_overrides)
    settings_ok, confirmed_settings = _settings_confirmed(effective_settings, actual_settings)
    if not effective_settings:
        settings_ok = True
    runtime_settings = (
        runtime.get("process_settings")
        if isinstance(runtime.get("process_settings"), dict)
        else {}
    )
    numeric_overrides = _effective_numeric_process_settings({}, process_overrides)
    overrides_applied = not numeric_overrides or _settings_confirmed(
        numeric_overrides, runtime_settings,
    )[0]
    analysis = meta.get("analysis") if isinstance(meta.get("analysis"), dict) else {}
    # IDs alone cannot prove that selected temperatures, fans or retraction
    # parameters survived native materialization and CLI profile loading.
    import hashlib
    import json
    filament_parameter_proof = []
    heater_commands = meta.get("heater_commands") or []
    for channel_index, (selected_item, applied_item) in enumerate(zip(selected_filaments, applied_filaments), 1):
        profile = selected_item["selected_profile"]
        profile_hash = hashlib.sha256(json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        expected_parameters = applied_item.get("parameter_settings") or {}
        matches = bool(expected_parameters and applied_item.get("selected_profile_sha256") == profile_hash)
        confirmed_keys = []
        mismatched_keys = []
        for key, expected in expected_parameters.items():
            actual = actual_settings.get(key)
            values = _normalized_setting_values(actual) if actual is not None else []
            expected_values = _normalized_setting_values(expected)
            matched = len(expected_values) == 1 and bool(values) and ((len(values) == 1 and values[0] == expected_values[0]) or (len(values) >= channel_index and values[channel_index - 1] == expected_values[0]))
            if matched: confirmed_keys.append(key)
            else: mismatched_keys.append(key)
        matches = matches and not mismatched_keys
        thermal_commands_confirmed = True
        for key in ("nozzle_temperature", "nozzle_temperature_initial_layer"):
            requested = expected_parameters.get(key)
            if requested is None:
                thermal_commands_confirmed = False
                continue
            expected_value = float(_normalized_setting_values(requested)[0][1])
            if not any(isinstance(command, dict) and command.get("channel") == channel_index
                       and command.get("command") in {"M104", "M109", "M620.10", "M620.15"}
                       and abs(float(command.get("temperature_c", -1)) - expected_value) <= .01
                       for command in heater_commands):
                thermal_commands_confirmed = False
        chamber = expected_parameters.get("chamber_temperatures")
        if chamber is not None:
            chamber_value = float(_normalized_setting_values(chamber)[0][1])
            if not any(isinstance(command, dict) and command.get("command") in {"M141", "M191"}
                       and abs(float(command.get("temperature_c", -1)) - chamber_value) <= .01 for command in heater_commands):
                thermal_commands_confirmed = False
        filament_parameter_proof.append({"channel": channel_index, "profile_id": profile.get("id"),
                                         "confirmed": matches and thermal_commands_confirmed,
                                         "confirmed_keys": confirmed_keys, "mismatched_keys": mismatched_keys,
                                         "thermal_commands_confirmed": thermal_commands_confirmed,
                                         "advisory_parameters": applied_item.get("advisory_parameters") or []})
    filament_parameters_confirmed = bool(filament_parameter_proof) and len(filament_parameter_proof) == len(selected_filaments) and all(item["confirmed"] for item in filament_parameter_proof)
    gcode_confirmed = bool(
        applied
        and filament_parameters_confirmed
        and settings_ok
        and overrides_applied
        and analysis.get("layer_count")
        and _materials_confirmed(applied_filaments, analysis)
    )
    numeric_value_proof = []
    proof_fields = [
        ("layer_height", "Schichthöhe", "mm"),
        ("outer_wall_speed", "Außenwand", "mm/s"),
        ("inner_wall_speed", "Innenwand", "mm/s"),
    ]
    proof_fields.extend(field for field in (
        ('initial_layer_print_height', 'Erste Schicht', 'mm'),
        ('wall_loops', 'Wandlinien', 'Linien'),
        ('top_shell_layers', 'Deckschichten', 'Schichten'),
        ('bottom_shell_layers', 'Bodenschichten', 'Schichten'),
        ('sparse_infill_density', 'Füllgrad', '%'),
        ('travel_speed', 'Verfahrgeschwindigkeit', 'mm/s'),
        ('line_width', 'Linienbreite', 'mm'),
        ('outer_wall_line_width', 'Außenwand-Linienbreite', 'mm'),
        ('inner_wall_line_width', 'Innenwand-Linienbreite', 'mm'),
        ('top_surface_line_width', 'Deckflächen-Linienbreite', 'mm'),
        ('support_line_width', 'Support-Linienbreite', 'mm'),
        ('sparse_infill_speed', 'Infillgeschwindigkeit', 'mm/s'),
        ('internal_solid_infill_speed', 'Massivfüllung-Geschwindigkeit', 'mm/s'),
        ('top_surface_speed', 'Deckflächengeschwindigkeit', 'mm/s'),
        ('initial_layer_speed', 'Geschwindigkeit erste Schicht', 'mm/s'),
        ('bridge_speed', 'Brückengeschwindigkeit', 'mm/s'),
        ('support_top_z_distance', 'Supportabstand oben', 'mm'),
        ('support_bottom_z_distance', 'Supportabstand unten', 'mm'),
        ('support_object_xy_distance', 'Supportabstand seitlich', 'mm'),
        ('support_interface_spacing', 'Support-Interface-Abstand', 'mm'),
        ('support_interface_top_layers', 'Support-Interfaceschichten oben', 'Schichten'),
        ('support_interface_bottom_layers', 'Support-Interfaceschichten unten', 'Schichten'),
    ) if field[0] in effective_settings)
    for key, label, unit in proof_fields:
        requested = effective_settings.get(key)
        observed = actual_settings.get(key)
        materialized = runtime_settings.get(key) if process_applied else None
        runtime_matches = (
            requested is not None and materialized is not None
            and _normalized_setting_values(requested) == _normalized_setting_values(materialized)
        )
        gcode_matches = (
            requested is not None and observed is not None
            and _normalized_setting_values(requested) == _normalized_setting_values(observed)
        )
        mismatch = requested is not None and (
            (materialized is not None and not runtime_matches)
            or (observed is not None and not gcode_matches)
        )
        numeric_value_proof.append({
            "key": key, "label": label, "unit": unit,
            "profile_value": settings.get(key),
            "requested_value": requested,
            "applied_value": materialized,
            "gcode_value": observed,
            "overridden": key in numeric_overrides,
            "status": "mismatch" if mismatch else (
                "confirmed" if applied and runtime_matches and gcode_matches
                else "unverified"
            ),
        })
    return {
        "selected": selected,
        "applied": applied,
        "gcode_confirmed": gcode_confirmed,
        "process": {
            "profile_id": str(selected_process.get("profile_id") or ""),
            "name": str(selected_process.get("name") or ""),
            "contract_sha256": str(
                selected_process.get("contract_sha256") or ""
            ),
            "selected_setting_count": len(settings),
            "effective_setting_count": len(effective_settings),
            "numeric_value_proof": numeric_value_proof,
            "gcode_confirmed_setting_count": confirmed_settings,
        },
        "filament_parameter_proof": filament_parameter_proof,
        "filament_parameters_confirmed": filament_parameters_confirmed,
        "filament_profile_count": len(selected_filaments),
        "material_channel_count": len(applied_filaments),
        "confirmation_source": (
            "parsed_gcode_header_and_toolpath"
            if gcode_confirmed
            else "pending_gcode_analysis"
            if applied
            else "pending_native_materialization"
            if selected
            else "selection_incomplete"
        ),
    }


def _server_job(
    payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    artifact_name: str | None = None,
    artifact_size: int | None = None,
    artifact_digest: str | None = None,
) -> dict[str, Any]:
    raw_id = str(payload.get("job_id", ""))
    raw_status = str(payload.get("status", "unknown"))
    status = {
        "queued": "queued",
        "slicing": "running",
        "completed": "succeeded",
        "failed": "failed",
        "cancelled": "cancelled",
    }.get(raw_status, raw_status)
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    engine_result = payload.get("engine_result") if isinstance(payload.get("engine_result"), dict) else {}
    material_plan = job.get("material_plan") if isinstance(job.get("material_plan"), dict) else {}
    process_overrides = job.get("process_overrides") if isinstance(job.get("process_overrides"), dict) else {}
    selected_process = process_overrides.get("selected_process_profile") if isinstance(process_overrides.get("selected_process_profile"), dict) else {}
    raw_filaments = material_plan.get("filaments")
    filaments = raw_filaments if isinstance(raw_filaments, list) else []
    try:
        raw_plate_index = job.get("requested_plate_index")
        if raw_plate_index is None:
            raw_plate_index = engine_result.get("plate_index")
        requested_plate_index = max(0, int(raw_plate_index or 0))
    except (TypeError, ValueError):
        requested_plate_index = 0
    engine_metrics = _engine_result_metrics(engine_result, requested_plate_index)
    consumption = metadata.get("consumption") if metadata else None
    analysis = metadata.get("analysis") if metadata else None
    terminal = status in {"succeeded", "failed", "cancelled", "interrupted"}

    def prefer(primary: object, fallback: object) -> object:
        return primary if primary is not None else fallback

    return {
        "id": SERVER_PREFIX + raw_id,
        "project_name": project_name_from_server_payload(payload, raw_id),
        "status": status,
        "created_at": job.get("created_at"),
        "started_at": progress.get("started_at"),
        "updated_at": progress.get("updated_at") or payload.get("status_updated_at"),
        "finished_at": payload.get("status_updated_at") if terminal else None,
        "error": result.get("error") or payload.get("error"),
        "output_size_bytes": artifact_size if artifact_size is not None else payload.get("download_size"),
        "output_filename": artifact_name or payload.get("download_name"),
        "output_file": artifact_name or payload.get("download_name"),
        "output_sha256": artifact_digest,
        "profiles": {
            "machine": job.get("native_machine_profile") or job.get("printer_profile"),
            "process": selected_process.get("profile_id") or job.get("process_profile"),
            "process_name": selected_process.get("name"),
            "process_contract_sha256": selected_process.get("contract_sha256"),
            "nozzle_diameter_mm": job.get("nozzle_diameter_mm"),
            "filaments": [item.get("name") for item in filaments if isinstance(item, dict)],
            "source": "native_slicing_server",
        },
        "slice_result": {
            "return_code": engine_metrics.get("return_code"),
            "error_string": engine_metrics.get("error_string"),
            "layer_height_mm": engine_metrics.get("layer_height_mm"),
            "plate_index": engine_metrics.get("plate_index"),
            "triangle_count": engine_metrics.get("triangle_count"),
            "print_time_seconds": prefer(metadata.get("print_time_seconds") if metadata else None, engine_metrics.get("print_time_seconds")),
            "model_time_seconds": prefer(metadata.get("model_time_seconds") if metadata else None, engine_metrics.get("model_time_seconds")),
            "preparation_time_seconds": prefer(metadata.get("preparation_time_seconds") if metadata else None, engine_metrics.get("preparation_time_seconds")),
            "slice_time_ms": engine_metrics.get("slice_time_ms"),
            "filament_used_g": prefer(metadata.get("filament_used_g") if metadata else None, engine_metrics.get("filament_used_g")),
            "filament_length_mm": metadata.get("filament_length_mm") if metadata else None,
            "filament_volume_cm3": metadata.get("filament_volume_cm3") if metadata else None,
            "layer_count": metadata.get("layer_count") if metadata else None,
            "filament_change_count": prefer(metadata.get("filament_change_count") if metadata else None, engine_metrics.get("filament_change_count")),
            "material_channel_count": metadata.get("material_channel_count") if metadata else runtime.get("material_channel_count"),
            "warning": engine_metrics.get("warning"),
            "consumption": consumption,
            "analysis": analysis,
            "engine": result.get("engine") or job.get("engine"),
            "output_format": "gcode_3mf" if artifact_name else result.get("output_format") or job.get("output_format"),
        },
        "slicer_progress": progress,
        "runtime_summary": runtime,
        "engine_result": engine_result,
        "profile_application": _profile_application(job, runtime, metadata),
        "process_overrides": job.get("process_overrides") or {},
        "target_printer": job.get("target_printer") or {},
        "ams_material_plan": material_plan,
        "requested_plate_index": requested_plate_index,
        "backend": BACKEND_SERVER,
        "backend_name": "Slicing Server",
        "server_job_id": raw_id,
    }


def _effective_material_plan(
    catalog: dict[str, Any],
    material_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    plan = dict(material_plan or {})
    raw_filaments = plan.get("filaments")
    if not isinstance(raw_filaments, list):
        return plan
    if not all(isinstance(item, dict) for item in raw_filaments):
        raise SlicerServerConfigurationError(
            "Der AMS-Materialplan enthält ungültige Filamentdaten."
        )
    filaments = [dict(item) for item in raw_filaments]
    try:
        attach_selected_profiles(catalog, filaments)
    except ValueError as exc:
        raise SlicerServerConfigurationError(str(exc)) from exc
    plan["filaments"] = filaments
    return plan


class V6SlicerBackendRouter:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.session = async_get_clientsession(hass)

    async def async_provider(
        self,
        backend: str = BACKEND_SERVER,
    ) -> dict[str, Any]:
        normalize_backend(backend)
        try:
            async with self.session.get(
                f"{SERVER_ENDPOINT}/api/v1/info",
                timeout=ClientTimeout(total=10),
            ) as response:
                if response.status >= 400:
                    raise SlicerServerError(
                        f"Slicing Server HTTP {response.status}"
                    )
                info = await response.json(content_type=None)
            ready = str(info.get("status")) == "ready"
            server = {
                "configured": True,
                "reachable": True,
                **info,
            }
        except (
            ClientError,
            TimeoutError,
            SlicerServerError,
        ) as exc:
            ready = False
            server = {
                "configured": True,
                "reachable": False,
                "status": "unreachable",
                "message": str(exc),
            }
        return {
            "id": (
                "native_linux_slicing_server"
                if ready
                else "server_unavailable"
            ),
            "name": "Slicing Server",
            "mode": "native_gcode" if ready else "offline",
            "backend": BACKEND_SERVER,
            "capabilities": {
                "geometry_preview": True,
                "layer_preview": True,
                "plan_persistence": True,
                "gcode_generation": ready,
                "gcode_3mf_artifact": ready,
                "job_cancellation": False,
                "direct_print": ready,
                "detailed_gcode_analysis": ready,
                "prime_tower_safety_gate": ready,
                "printer_display_name": ready,
                "printer_thumbnail": ready,
            },
            "server": server,
            "disclaimer": (
                "Slicing läuft ausschließlich auf dem nativen "
                "Linux-Slicing-Server."
            ),
        }

    async def async_create_plate_job(
        self,
        backend: str,
        filename: str,
        model: bytes,
        _catalog: dict[str, Any],
        _plate_index: int,
        process_overrides: dict[str, Any] | None = None,
        *,
        target_printer: dict[str, Any] | None = None,
        material_plan: dict[str, Any] | None = None,
        selected_process_profile: dict[str, Any] | None = None,
        source_project_name: str | None = None,
        manual_release: bool = False,
    ) -> dict[str, Any]:
        normalize_backend(backend)
        printer_profile = _server_printer_profile(target_printer)
        nozzle_contract = resolve_nozzle_contract(_catalog, target_printer)
        validated_overrides = validate_process_overrides(
            process_overrides,
            nozzle_contract,
        )
        if not isinstance(selected_process_profile, dict):
            raise SlicerServerConfigurationError(
                "Das ausgewählte Prozessprofil besitzt keinen gültigen Slicing-Vertrag."
            )
        validated_overrides["require_selected_process_profile_contract"] = True
        validated_overrides["selected_process_profile"] = dict(
            selected_process_profile
        )
        target_context = {
            **(target_printer or {}),
            **contract_payload(nozzle_contract),
        }
        effective_material_plan = _effective_material_plan(
            _catalog,
            material_plan,
        )
        validated_overrides["require_execution_contract"] = True
        validated_overrides["execution_contract"] = bind_execution_contract(
            target_context, validated_overrides, effective_material_plan,
        )
        if str(source_project_name or "").strip():
            project_name = safe_project_name(
                source_project_name,
                "Druckauftrag",
            )
        else:
            project_name = await self.hass.async_add_executor_job(
                project_name_from_3mf,
                model,
                filename,
            )
        requested_plate_index = max(0, int(_plate_index))
        # The native worker accepts ASCII basenames of at most 200 characters.
        # Keep the original project title in metadata, not in the transport name.
        safe_name = re.sub(
            r"[^A-Za-z0-9._-]",
            "_",
            project_name,
        ).strip("._-") or "Druckauftrag"
        upload_prefix = (
            f"v6-{uuid4().hex[:10]}-plate-"
            f"{requested_plate_index + 1}-"
        )
        upload_name = f"{upload_prefix}{safe_name[:200 - len(upload_prefix) - 4]}.3mf"
        try:
            async with self.session.post(
                f"{SERVER_ENDPOINT}/api/v1/files/{upload_name}",
                data=model,
                headers={"Content-Type": "application/octet-stream"},
                timeout=ClientTimeout(total=300),
            ) as response:
                if response.status >= 400:
                    detail = await response.text()
                    raise SlicerServerError(
                        f"Server-Upload HTTP {response.status}: "
                        f"{detail[:300]}"
                    )
            request = {
                "job_id": f"v6-{uuid4().hex}",
                "project_name": project_name,
                "printer_profile": printer_profile,
                "engine": "auto",
                "input_file": upload_name,
                "process_profile": str(selected_process_profile.get("profile_id") or ""),
                "filament_profile": "ams_runtime",
                "output_format": "3mf",
                "requested_plate_index": requested_plate_index,
                "process_overrides": validated_overrides,
                "target_printer": target_context,
                "material_plan": effective_material_plan,
                "native_multimaterial": True,
                "manual_release": manual_release,
            }
            async with self.session.post(
                f"{SERVER_ENDPOINT}/api/v1/jobs",
                json=request,
                timeout=ClientTimeout(total=30),
            ) as response:
                if response.status >= 400:
                    detail = await response.text()
                    raise SlicerServerError(
                        f"Server-Slicing HTTP {response.status}: "
                        f"{detail[:300]}"
                    )
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError) as exc:
            raise SlicerServerError(
                f"Slicing Server nicht erreichbar: {exc}"
            ) from exc
        created = _server_job(payload)
        created["profile_application"] = _profile_application(request, {}, None)
        return created

    async def _server_job_payload(
        self,
        raw_id: str,
    ) -> dict[str, Any]:
        try:
            async with self.session.get(
                f"{SERVER_ENDPOINT}/api/v1/jobs/{raw_id}",
                timeout=ClientTimeout(total=15),
            ) as response:
                if response.status >= 400:
                    raise SlicerServerError(
                        f"Slicing Server HTTP {response.status}"
                    )
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError) as exc:
            raise SlicerServerError(
                f"Slicing Server nicht erreichbar: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise SlicerServerError(
                "Slicing Server lieferte keinen gültigen Auftrag."
            )
        return payload

    async def _server_completed_artifact(
        self,
        raw_id: str,
        payload: dict[str, Any],
    ) -> tuple[bytes, str, str, dict[str, Any]]:
        cached = _cached_artifact(raw_id)
        if cached is not None:
            return cached
        raw = await self._server_raw_artifact(raw_id)
        result = await self.hass.async_add_executor_job(
            _prepare_server_artifact,
            raw_id,
            payload,
            raw,
        )
        _store_artifact(raw_id, result)
        return result

    async def async_get_job(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        raw_id = native_job_id(job_id)
        try:
            payload = await self._server_job_payload(raw_id)
            # Job status must remain lightweight and live. Expensive G-code validation,
            # analysis and project-artifact preparation belong to /artifact and /toolpath.
            # The native server already exposes Bambu engine_result/runtime/progress here.
            # Reuse completed analysis only when /artifact or /toolpath has already produced it;
            # never trigger the expensive G-code analysis from the live status endpoint.
            metadata = _cached_metadata(raw_id)
            return _server_job(payload, metadata)
        except ValueError as exc:
            raise SlicerServerError(
                f"Sicherheitsprüfung des Slicergebnisses fehlgeschlagen: {exc}"
            ) from exc

    async def _server_raw_artifact(
        self,
        raw_id: str,
    ) -> bytes:
        try:
            async with self.session.get(
                f"{SERVER_ENDPOINT}/api/v1/jobs/{raw_id}/download",
                timeout=ClientTimeout(total=300),
            ) as response:
                if response.status >= 400:
                    raise SlicerServerError(
                        f"Server-Download HTTP {response.status}"
                    )
                return await response.read()
        except (ClientError, TimeoutError) as exc:
            raise SlicerServerError(
                f"Slicing Server nicht erreichbar: {exc}"
            ) from exc

    async def async_release_job(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """Release a queued job to start slicing."""
        raw_id = native_job_id(job_id)
        try:
            async with self.session.post(
                f"{SERVER_ENDPOINT}/api/v1/jobs/{raw_id}/release",
                timeout=ClientTimeout(total=30),
            ) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise SlicerServerError(
                        f"Slicerauftrag konnte nicht freigegeben werden: "
                        f"Server HTTP {response.status}"
                    )
        except (ClientError, TimeoutError) as exc:
            raise SlicerServerError(
                f"Slicing Server beim Freigeben nicht erreichbar: {exc}"
            ) from exc
        return payload if isinstance(payload, dict) else {}
    async def async_list_jobs(self) -> list[dict[str, Any]]:
        """List jobs from the fixed native slicing server."""
        try:
            async with self.session.get(
                f"{SERVER_ENDPOINT}/api/v1/jobs",
                timeout=ClientTimeout(total=30),
            ) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise SlicerServerError(
                        f"Sliceraufträge konnten nicht geladen werden: "
                        f"Server HTTP {response.status}"
                    )
        except (ClientError, TimeoutError) as exc:
            raise SlicerServerError(
                f"Slicing Server beim Laden nicht erreichbar: {exc}"
            ) from exc
        items = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise SlicerServerError(
                "Der Slicing Server lieferte keine gültige Auftragsliste."
            )
        return [
            _server_job(item)
            for item in items
            if isinstance(item, dict)
        ]

    async def async_delete_job(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """Delete one terminal job on the fixed native slicing server."""
        raw_id = native_job_id(job_id)
        try:
            async with self.session.delete(
                f"{SERVER_ENDPOINT}/api/v1/jobs/{raw_id}",
                timeout=ClientTimeout(total=45),
            ) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    detail = (
                        str(payload.get("error") or payload.get("message") or "")
                        if isinstance(payload, dict)
                        else ""
                    )
                    raise SlicerServerError(
                        f"Slicerauftrag konnte nicht gelöscht werden: "
                        f"Server HTTP {response.status}"
                        f"{f' – {detail}' if detail else ''}"
                    )
        except (ClientError, TimeoutError) as exc:
            raise SlicerServerError(
                f"Slicing Server beim Löschen nicht erreichbar: {exc}"
            ) from exc
        result = payload if isinstance(payload, dict) else None
        if not result or result.get("deleted") is not True:
            raise SlicerServerError(
                "Der Slicing Server hat die Löschung nicht bestätigt."
            )
        _COMPLETED_ARTIFACT_CACHE.pop(raw_id, None)
        return result

    async def async_artifact(
        self,
        job_id: str,
    ) -> tuple[bytes, str, str | None, str]:
        raw_id = native_job_id(job_id)
        payload = await self._server_job_payload(raw_id)
        if str(payload.get("status")) != "completed":
            raise SlicerServerError(
                "Der Slicerauftrag besitzt noch kein fertiges Artefakt."
            )
        content, filename, digest, _metadata = (
            await self._server_completed_artifact(raw_id, payload)
        )
        return content, filename, digest, "model/3mf"

