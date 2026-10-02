#!/usr/bin/env python3
"""Create one native Bambu CLI assemble job from a V6 3MF and AMS plan."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import re
import struct
from pathlib import Path
from typing import Any, Iterable
import importlib.util
import sys

if __package__:
    from .three_mf_mesh_graph import mesh_instances
else:
    _GRAPH_PATH = Path(__file__).with_name("three_mf_mesh_graph.py")
    _GRAPH_SPEC = importlib.util.spec_from_file_location(
        "ultimate_3d_studio_v6_three_mf_mesh_graph",
        _GRAPH_PATH,
    )
    if _GRAPH_SPEC is None or _GRAPH_SPEC.loader is None:
        raise ImportError(f"3MF-Graphmodul konnte nicht geladen werden: {_GRAPH_PATH}")
    _GRAPH_MODULE = importlib.util.module_from_spec(_GRAPH_SPEC)
    sys.modules[_GRAPH_SPEC.name] = _GRAPH_MODULE
    _GRAPH_SPEC.loader.exec_module(_GRAPH_MODULE)
    mesh_instances = _GRAPH_MODULE.mesh_instances

_METADATA_KEYS = {
    "name", "type", "from", "instantiation", "inherits", "include",
    "setting_id", "filament_id", "compatible_printers", "compatible_prints",
    "compatible_printers_condition", "compatible_prints_condition",
    "model_id", "dev_model_name",
}
_MODEL_SUFFIXES = {
    "a1": ("@BBL A1",),
    "a1_mini": ("@BBL A1M", "@BBL A1 mini"),
    "p1s": ("@BBL P1S", "@BBL P1P"),
    "p1p": ("@BBL P1P", "@BBL P1S"),
    "x1c": ("@BBL X1C", "@BBL X1"),
    "x1": ("@BBL X1", "@BBL X1C"),
    "x1e": ("@BBL X1E", "@BBL X1"),
}

_PROCESS_OVERRIDE_MAP = {
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
}
_PROCESS_OVERRIDE_RULES = {
    "layer_height_mm": (.04, .56, False),
    "first_layer_height_mm": (.04, .56, False),
    "walls": (0, None, True),
    "top_shell_layers": (0, None, True),
    "bottom_shell_layers": (0, None, True),
    "infill_percent": (0, 100, False),
    "outer_wall_speed_mm_s": (1, 500, False),
    "inner_wall_speed_mm_s": (1, 500, False),
    "travel_speed_mm_s": (1, 500, False),
    **{key: (.01, None, False) for key in ("line_width_mm", "outer_wall_line_width_mm", "inner_wall_line_width_mm", "top_surface_line_width_mm", "support_line_width_mm")},
    **{key: (1, None, False) for key in ("sparse_infill_speed_mm_s", "internal_solid_infill_speed_mm_s", "top_surface_speed_mm_s", "initial_layer_speed_mm_s", "bridge_speed_mm_s", "gap_infill_speed_mm_s", "solid_infill_speed_mm_s", "ironing_speed_mm_s", "support_speed_mm_s", "support_interface_speed_mm_s")},
    "bridge_flow_ratio": (0, None, False),
    "support_top_z_distance_mm": (0, None, False),
    "support_bottom_z_distance_mm": (0, None, False),
    "support_object_xy_distance_mm": (0, None, False),
    "support_interface_spacing_mm": (0, None, False),
    "support_interface_top_layers": (0, None, True),
    "support_interface_bottom_layers": (0, None, True),
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Ungültige JSON-Datei: {path}")
    return value


def _safe_name(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-.")
    return text[:120] or "part"


def _canonical_model(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    for names, key in (
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


def _find_named(directory: Path, name: str) -> Path:
    direct = directory / f"{name}.json"
    if direct.is_file():
        return direct
    matches = [path for path in directory.rglob(f"{name}.json") if path.is_file()]
    if len(matches) != 1:
        raise FileNotFoundError(f"Profil nicht eindeutig gefunden: {name}")
    return matches[0]


def _resolve_profile(
    directory: Path,
    path: Path,
    seen: set[Path] | None = None,
) -> dict[str, Any]:
    active = set() if seen is None else seen
    resolved_path = path.resolve()
    if resolved_path in active:
        raise ValueError(f"Zyklische Profilvererbung: {path.name}")
    active.add(resolved_path)
    payload = _json(path)
    merged: dict[str, Any] = {}
    parent = str(payload.get("inherits") or "").strip()
    if parent:
        merged.update(_resolve_profile(directory, _find_named(directory, parent), active))
    includes = payload.get("include")
    if isinstance(includes, list):
        for item in includes:
            include_payload = _json(_find_named(directory, str(item)))
            for key, value in include_payload.items():
                if key not in _METADATA_KEYS:
                    merged[key] = value
    for key, value in payload.items():
        if key not in {"inherits", "include"}:
            merged[key] = value
    active.remove(resolved_path)
    return merged


def _profile_candidates(
    directory: Path,
    filament_id: str,
    material: str,
) -> list[tuple[Path, dict[str, Any]]]:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    material_key = material.casefold().strip()
    for path in directory.rglob("*.json"):
        try:
            payload = _json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        profile_id = str(payload.get("filament_id") or "").strip()
        profile_type = " ".join(
            str(item) for item in payload.get("filament_type", [])
        ).casefold()
        if filament_id and profile_id == filament_id:
            candidates.append((path, payload))
        elif not filament_id and material_key and material_key in profile_type:
            candidates.append((path, payload))
    return candidates


def _selected_profile_path(
    directory: Path,
    filament: dict[str, Any],
    model: str,
) -> Path | None:
    selected = filament.get("selected_profile")
    if not isinstance(selected, dict):
        return None
    payload = selected.get("payload") if isinstance(selected.get("payload"), dict) else {}
    explicit = str(
        payload.get("profile_path") or payload.get("native_profile_path") or ""
    ).strip()
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = directory.parent.parent / explicit
        if path.is_file():
            return path
        raise FileNotFoundError(f"Ausgewähltes Filamentprofil fehlt: {explicit}")

    inherited = str(payload.get("inherits") or "").strip().strip('"')
    if inherited:
        return _find_named(directory, inherited)

    names = {
        str(selected.get("name") or "").strip().casefold(),
        str(payload.get("name") or "").strip().casefold(),
        str(payload.get("filament_settings_id") or "").strip().strip('"').casefold(),
        str(payload.get("bambu_profile_name") or "").strip().casefold(),
        str(payload.get("native_profile_name") or "").strip().casefold(),
    } - {""}
    identifiers = {
        str(payload.get("setting_id") or "").strip(),
        str(payload.get("filament_id") or "").strip(),
        str((payload.get("_bambu_cloud") or {}).get("base_id") or "").strip()
        if isinstance(payload.get("_bambu_cloud"), dict)
        else "",
    } - {""}
    suffixes = _MODEL_SUFFIXES.get(model, ())
    ranked: list[tuple[int, int, int, str, Path]] = []
    for path in directory.rglob("*.json"):
        try:
            candidate = _json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        candidate_name = str(candidate.get("name") or path.stem)
        exact_name = int(
            candidate_name.casefold() in names or path.stem.casefold() in names
        )
        exact_id = int(
            bool(
                identifiers
                & {
                    str(candidate.get("setting_id") or "").strip(),
                    str(candidate.get("filament_id") or "").strip(),
                }
            )
        )
        if not exact_name and not exact_id:
            continue
        model_match = int(
            any(suffix.casefold() in candidate_name.casefold() for suffix in suffixes)
        )
        ranked.append((-exact_id, -exact_name, -model_match, candidate_name, path))
    if not ranked:
        raise FileNotFoundError(
            f"Das ausgewählte Filamentprofil {selected.get('name')} "
            "besitzt kein natives Bambu-Basisprofil."
        )
    ranked.sort()
    return ranked[0][-1]


def _select_filament_profile(
    directory: Path,
    filament: dict[str, Any],
    model: str,
) -> Path:
    selected = _selected_profile_path(directory, filament, model)
    if selected is not None:
        return selected
    explicit = str(filament.get("profile_path") or "").strip()
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = directory.parent.parent / explicit
        if path.is_file():
            return path
        raise FileNotFoundError(f"Filamentprofil fehlt: {explicit}")
    filament_id = str(
        filament.get("filament_id") or filament.get("tray_id") or ""
    ).strip()
    material = str(filament.get("material") or "").strip()
    candidates = _profile_candidates(directory, filament_id, material)
    if not candidates:
        generic = f"Generic {material.upper()}" if material else "Generic PLA"
        candidates = [
            (path, _json(path)) for path in directory.rglob(f"{generic}*.json")
        ]
    if not candidates:
        raise FileNotFoundError(
            f"Kein Bambu-Filamentprofil für {filament_id or material}"
        )
    suffixes = _MODEL_SUFFIXES.get(model, ())
    ranked: list[tuple[int, int, int, str, Path]] = []
    for path, payload in candidates:
        name = str(payload.get("name") or path.stem)
        compatible = " ".join(
            str(item) for item in payload.get("compatible_printers", [])
        )
        model_match = int(
            any(suffix.casefold() in name.casefold() for suffix in suffixes)
        )
        compatible_match = int(model.replace("_", " ") in compatible.casefold())
        generic_penalty = int("@base" in name.casefold())
        ranked.append(
            (-model_match, -compatible_match, generic_penalty, name, path)
        )
    ranked.sort()
    return ranked[0][-1]


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _as_profile_value(value: Any, reference: Any = None) -> Any:
    if isinstance(reference, list):
        if isinstance(value, list):
            return value
        return [str(value)]
    return value


def _apply_selected_profile_payload(
    profile: dict[str, Any],
    filament: dict[str, Any],
) -> dict[str, Any]:
    selected = filament.get("selected_profile")
    if not isinstance(selected, dict):
        return profile
    payload = selected.get("payload") if isinstance(selected.get("payload"), dict) else {}
    result = dict(profile)
    result["name"] = str(selected.get("name") or result.get("name") or "")
    direct_prefixes = (
        "filament_",
        "nozzle_",
        "hot_plate_",
        "textured_plate_",
        "cool_plate_",
        "eng_plate_",
        "smooth_plate_",
        "supertack_plate_",
    )
    for key, value in payload.items():
        if key in _METADATA_KEYS or key.startswith("_"):
            continue
        if key in result or key.startswith(direct_prefixes):
            result[key] = _as_profile_value(value, result.get(key))
    mappings = {
        "flow_ratio": "filament_flow_ratio",
        "max_volumetric_speed_mm3_s": "filament_max_volumetric_speed",
        "density_g_cm3": "filament_density",
        "diameter_mm": "filament_diameter",
    }
    for source, target in mappings.items():
        if source in payload:
            result[target] = [str(payload[source])]
    nozzle = payload.get("nozzle_temperature_c")
    if isinstance(nozzle, (int, float, str)):
        result["nozzle_temperature"] = [str(nozzle)]
        result["nozzle_temperature_initial_layer"] = [str(nozzle)]
    bed = payload.get("bed_temperature_c")
    if isinstance(bed, (int, float, str)):
        for key in (
            "hot_plate_temp",
            "hot_plate_temp_initial_layer",
            "textured_plate_temp",
            "textured_plate_temp_initial_layer",
            "eng_plate_temp",
            "eng_plate_temp_initial_layer",
        ):
            result[key] = [str(bed)]
    return result


def _number(value: object, fallback: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(result):
        return fallback
    return result


def _required_override_number(
    overrides: dict[str, Any],
    key: str,
    minimum: float,
    maximum: float | None,
) -> float | None:
    value = overrides.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{key} ist ungültig")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} ist ungültig") from exc
    if not math.isfinite(parsed) or parsed < minimum or (maximum is not None and parsed > maximum):
        raise ValueError(f"{key} ist außerhalb des gültigen Bereichs")
    return parsed


def _apply_process_overrides(process: dict[str, Any], overrides: dict[str, Any]) -> None:
    for override_key, process_key in _PROCESS_OVERRIDE_MAP.items():
        minimum, maximum, integer = _PROCESS_OVERRIDE_RULES[override_key]
        value = _required_override_number(overrides, override_key, minimum, maximum)
        if value is None:
            continue
        if integer:
            if not value.is_integer():
                raise ValueError(f"{override_key} erfordert eine ganze Zahl")
            applied: Any = int(value)
        elif override_key == "infill_percent":
            applied = f"{value:g}%"
        else:
            applied = _clean_number(value)
        process[process_key] = _as_profile_value(applied, process.get(process_key))


def _validated_layer_height_ranges(
    overrides: dict[str, Any],
) -> list[dict[str, float]]:
    ranges = overrides.get("layer_height_ranges")
    if ranges is None:
        return []
    if not isinstance(ranges, list):
        raise ValueError("layer_height_ranges ist ungültig")
    if len(ranges) > 32:
        raise ValueError("layer_height_ranges enthält zu viele Bereiche")
    min_layer = _number(overrides.get("min_layer_height_mm"), .04)
    max_layer = _number(overrides.get("max_layer_height_mm"), .56)
    normalized: list[dict[str, float]] = []
    previous_max = 0.0
    for index, item in enumerate(ranges, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"layer_height_ranges[{index}] ist ungültig")
        min_z = _required_override_number(
            item,
            "min_z_mm" if item.get("min_z_mm") is not None else "min_z",
            0.0,
            256.0,
        )
        max_z = _required_override_number(
            item,
            "max_z_mm" if item.get("max_z_mm") is not None else "max_z",
            0.0,
            256.0,
        )
        height = _required_override_number(
            item,
            "layer_height_mm" if item.get("layer_height_mm") is not None else "layer_height",
            min_layer,
            max_layer,
        )
        if min_z is None or max_z is None or height is None or max_z <= min_z:
            raise ValueError(f"layer_height_ranges[{index}] ist ungültig")
        if min_z < previous_max:
            raise ValueError("layer_height_ranges darf sich nicht überlappen")
        normalized.append({
            "min_z": min_z,
            "max_z": max_z,
            "layer_height": height,
        })
        previous_max = max_z
    return normalized


def _native_height_ranges(
    ranges: list[dict[str, float]],
) -> list[dict[str, Any]]:
    return [
        {
            "min_z": item["min_z"],
            "max_z": item["max_z"],
            "range_params": {
                "layer_height": _clean_number(item["layer_height"]),
            },
        }
        for item in ranges
    ]


def _plate_value(
    purge: dict[str, Any],
    plural_key: str,
    singular_key: str,
    plate_index: int,
    fallback: float,
) -> float:
    values = purge.get(plural_key)
    if isinstance(values, list) and values:
        selected = values[min(max(plate_index, 0), len(values) - 1)]
        return _number(selected, fallback)
    return _number(purge.get(singular_key), fallback)


def _clean_number(value: float) -> str:
    rounded = round(value, 4)
    return str(int(rounded)) if rounded.is_integer() else f"{rounded:.4f}".rstrip("0").rstrip(".")


def _tower_geometry(
    purge: dict[str, Any],
    overrides: dict[str, Any],
    plate_index: int,
) -> dict[str, Any]:
    plate_width = max(1.0, _number(overrides.get("build_plate_width_mm"), 256.0))
    plate_depth = max(1.0, _number(overrides.get("build_plate_depth_mm"), 256.0))
    width = max(10.0, min(80.0, _number(purge.get("width_mm"), 35.0)))
    brim = max(0.0, min(20.0, _number(purge.get("brim_width_mm"), 3.0)))
    safety_margin = brim + 4.0
    max_x = plate_width - width - safety_margin
    max_y = plate_depth - width - safety_margin
    if max_x < safety_margin or max_y < safety_margin:
        raise ValueError(
            "Der Reinigungsturm passt mit Breite und Brim nicht auf die Druckplatte."
        )

    fallback_x = max(safety_margin, min(max_x, plate_width - width - safety_margin))
    fallback_y = max(safety_margin, min(max_y, plate_depth - width - safety_margin))
    requested_x = _plate_value(
        purge, "positions_x", "position_x", plate_index, fallback_x
    )
    requested_y = _plate_value(
        purge, "positions_y", "position_y", plate_index, fallback_y
    )
    effective_x = max(safety_margin, min(max_x, requested_x))
    effective_y = max(safety_margin, min(max_y, requested_y))
    return {
        "plate_index": plate_index,
        "plate_width_mm": plate_width,
        "plate_depth_mm": plate_depth,
        "width_mm": width,
        "brim_width_mm": brim,
        "requested_x": requested_x,
        "requested_y": requested_y,
        "position_x": effective_x,
        "position_y": effective_y,
        "clamped": (
            abs(effective_x - requested_x) > 0.0001
            or abs(effective_y - requested_y) > 0.0001
        ),
        "bounds": {
            "min_x": effective_x - brim,
            "min_y": effective_y - brim,
            "max_x": effective_x + width + brim,
            "max_y": effective_y + width + brim,
        },
    }



def _contract_digest(contract: dict[str, Any]) -> str:
    return sha256(
        json.dumps(
            contract,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _apply_selected_process_profile(
    process: dict[str, Any],
    process_source: Path,
    process_directory: Path,
    overrides: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = overrides.get("selected_process_profile")
    if not isinstance(contract, dict):
        if overrides.get("require_selected_process_profile_contract") is True:
            raise ValueError("Der exakte Prozessprofilvertrag fehlt.")
        return process, {
            "applied": False,
            "legacy_request": True,
            "reason": "profile_contract_not_requested",
        }
    supplied_digest = str(contract.get("contract_sha256") or "")
    body = dict(contract)
    body.pop("contract_sha256", None)
    if supplied_digest != _contract_digest(body):
        raise ValueError("Der Prozessprofilvertrag ist nicht integer.")
    if body.get("schema_version") != 1:
        raise ValueError("Der Prozessprofilvertrag hat eine unbekannte Version.")
    expected_base = "BBL/process/" + process_source.resolve().relative_to(
        process_directory.resolve()
    ).as_posix()
    if str(body.get("native_base_profile") or "") != expected_base:
        raise ValueError(
            "Das Prozessprofil passt nicht zum validierten nativen Basisprofil."
        )
    profile_id = str(body.get("profile_id") or "")
    name = str(body.get("name") or "")
    settings = body.get("settings")
    if not profile_id or not name or not isinstance(settings, dict) or not settings:
        raise ValueError("Der Prozessprofilvertrag ist unvollständig.")

    applied = dict(process)
    for key, value in settings.items():
        if not isinstance(key, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]{0,127}",
            key,
        ):
            raise ValueError("Der Prozessprofilvertrag enthält einen ungültigen Schlüssel.")
        if "gcode" in key.casefold():
            raise ValueError(
                "Prozessprofile dürfen keine G-Code-Vorlage überschreiben."
            )
        if key == "layer_height":
            value = _clean_number(_required_override_number(
                {"layer_height": value},
                "layer_height",
                .04,
                .56,
            ) or 0.2)
        applied[key] = _as_profile_value(value, applied.get(key))
    return applied, {
        "applied": True,
        "profile_id": profile_id,
        "name": name,
        "source": str(body.get("source") or ""),
        "materialization_policy": str(
            body.get("materialization_policy") or ""
        ),
        "native_base_profile": expected_base,
        "contract_sha256": supplied_digest,
        "applied_setting_count": len(settings),
    }


def _materialize_process(
    process_source: Path,
    process_directory: Path,
    filament_directory: Path,
    filaments: list[dict[str, Any]],
    model: str,
    overrides: dict[str, Any],
    purge: dict[str, Any],
    plate_index: int,
) -> tuple[
    dict[str, Any],
    list[Path],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    process = _resolve_profile(process_directory, process_source)
    process, process_profile_proof = _apply_selected_process_profile(
        process,
        process_source,
        process_directory,
        overrides,
    )
    selected_paths: list[Path] = []
    resolved_profiles: list[dict[str, Any]] = []
    for filament in filaments:
        path = _select_filament_profile(filament_directory, filament, model)
        selected_paths.append(path)
        resolved_profiles.append(
            _apply_selected_profile_payload(
                _resolve_profile(filament_directory, path),
                filament,
            )
        )

    option_keys: set[str] = set()
    for profile in resolved_profiles:
        option_keys.update(
            key
            for key, value in profile.items()
            if isinstance(value, list) and key not in _METADATA_KEYS
        )
    for key in sorted(option_keys):
        values: list[Any] = []
        for profile in resolved_profiles:
            value = _first(profile.get(key))
            if value is None:
                value = _first(process.get(key))
            if value is None:
                continue
            values.append(value)
        if len(values) == len(filaments):
            process[key] = values

    colors = [str(item.get("color") or "#808080") for item in filaments]
    materials = [
        str(item.get("material") or "unknown").upper() for item in filaments
    ]
    ids = [
        str(item.get("filament_id") or item.get("tray_id") or "")
        for item in filaments
    ]
    names = [
        str(profile.get("name") or path.stem)
        for profile, path in zip(resolved_profiles, selected_paths)
    ]
    count = len(filaments)
    tower_enabled = count > 1 and purge.get("enabled") is not False
    process.update(
        {
            "filament_colour": colors,
            "filament_type": materials,
            "filament_ids": ids,
            "filament_settings_id": names,
            "filament_is_support": ["0"] * count,
            "filament_self_index": [
                str(index) for index in range(1, count + 1)
            ],
            "filament_map": ["1"] * count,
            "filament_map_2": ["1"] * count,
            "filament_nozzle_map": ["1"] * count,
            "physical_extruder_map": ["0"],
            "enable_prime_tower": "1" if tower_enabled else "0",
        }
    )
    for key, default in (
        ("filament_diameter", "1.75"),
        ("filament_density", "1.24"),
        ("filament_flow_ratio", "1"),
        ("filament_max_volumetric_speed", "2"),
        ("nozzle_temperature", "200"),
        ("nozzle_temperature_initial_layer", "200"),
    ):
        values = process.get(key)
        if not isinstance(values, list) or len(values) != count:
            process[key] = [str(_first(values) or default)] * count

    multiplier = max(
        0.1,
        min(3.0, _number(purge.get("flush_multiplier"), 1.0)),
    )
    matrix = purge.get("flush_volumes_matrix")
    vector = purge.get("flush_volumes_vector")
    if isinstance(matrix, list) and len(matrix) == count * count:
        process["flush_volumes_matrix"] = [str(value) for value in matrix]
    else:
        off_diagonal = str(int(round(280 * multiplier)))
        process["flush_volumes_matrix"] = [
            "0" if left == right else off_diagonal
            for left in range(count)
            for right in range(count)
        ]
    if isinstance(vector, list) and len(vector) == count * 2:
        process["flush_volumes_vector"] = [str(value) for value in vector]
    else:
        process["flush_volumes_vector"] = ["140"] * (count * 2)

    tower = _tower_geometry(purge, overrides, plate_index)
    process["prime_tower_width"] = _clean_number(float(tower["width_mm"]))
    process["prime_tower_brim_width"] = _clean_number(
        float(tower["brim_width_mm"])
    )
    # These are the actual option names consumed and echoed by Bambu Studio.
    process["wipe_tower_x"] = _clean_number(float(tower["position_x"]))
    process["wipe_tower_y"] = _clean_number(float(tower["position_y"]))
    process.pop("prime_tower_position_x", None)
    process.pop("prime_tower_position_y", None)

    adhesion = str(overrides.get("adhesion_mode") or "none")
    support = str(overrides.get("support_mode") or "off")
    process["brim_type"] = "outer_only" if adhesion == "brim" else "no_brim"
    process["brim_width"] = (
        str(overrides.get("brim_width_mm") or 0)
        if adhesion == "brim"
        else "0"
    )
    process["raft_layers"] = (
        str(overrides.get("raft_layers") or 0)
        if adhesion == "raft"
        else "0"
    )
    process["enable_support"] = "0" if support == "off" else "1"
    support_style = str(overrides.get("support_style") or "standard")
    process["support_type"] = (
        "tree(auto)" if support == "tree" else "normal(auto)"
    )
    process["support_style"] = support_style
    process["v6_support_style"] = support_style
    process["support_on_build_plate_only"] = (
        "1" if overrides.get("support_build_plate_only", True) else "0"
    )
    process["support_threshold_angle"] = str(
        overrides.get("support_threshold_angle") or 30
    )
    _apply_process_overrides(process, overrides)
    return process, selected_paths, resolved_profiles, tower, process_profile_proof


def _triangle_normal(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
) -> tuple[float, float, float]:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = (
        uy * vz - uz * vy,
        uz * vx - ux * vz,
        ux * vy - uy * vx,
    )
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / length, ny / length, nz / length


def _write_binary_stl(
    path: Path,
    name: str,
    vertices: list[tuple[float, float, float]],
    triangles: Iterable[tuple[int, int, int]],
) -> int:
    records: list[bytes] = []
    for v1, v2, v3 in triangles:
        a, b, c = vertices[v1], vertices[v2], vertices[v3]
        normal = _triangle_normal(a, b, c)
        records.append(struct.pack("<12fH", *normal, *a, *b, *c, 0))
    header = name.encode("ascii", errors="replace")[:80].ljust(80, b"\0")
    path.write_bytes(
        header + struct.pack("<I", len(records)) + b"".join(records)
    )
    return len(records)



def _plate_placement_offset(
    instances: Iterable[Any],
    plate_width_mm: float,
    plate_depth_mm: float,
) -> tuple[float, float]:
    bounds = [
        vertex
        for instance in instances
        for vertex in instance.vertices
    ]
    if not bounds:
        return 0.0, 0.0
    min_x = min(vertex[0] for vertex in bounds)
    max_x = max(vertex[0] for vertex in bounds)
    min_y = min(vertex[1] for vertex in bounds)
    max_y = max(vertex[1] for vertex in bounds)
    width = max_x - min_x
    depth = max_y - min_y
    if width > plate_width_mm or depth > plate_depth_mm:
        raise ValueError(
            "Das 3MF-Modell ist größer als die gewählte Druckplatte"
        )
    offset_x = (
        (plate_width_mm - width) / 2 - min_x
        if min_x < 0 or max_x > plate_width_mm
        else 0.0
    )
    offset_y = (
        (plate_depth_mm - depth) / 2 - min_y
        if min_y < 0 or max_y > plate_depth_mm
        else 0.0
    )
    return offset_x, offset_y


def _extract_parts(
    input_3mf: Path,
    parts_dir: Path,
    assignments: dict[str, int],
    *,
    default_channel: int | None = None,
    material_channel_count: int | None = None,
    plate_width_mm: float = 256.0,
    plate_depth_mm: float = 256.0,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    parts_dir.mkdir(parents=True, exist_ok=True)
    manifest_objects: list[dict[str, Any]] = []
    triangle_total = 0
    painted_triangle_count = 0
    painted_channels: set[int] = set()
    instances = mesh_instances(input_3mf)
    offset_x, offset_y = _plate_placement_offset(
        instances,
        plate_width_mm,
        plate_depth_mm,
    )
    for order, instance in enumerate(instances, start=1):
        channel = assignments.get(instance.logical_object_id, default_channel)
        if channel is None:
            raise ValueError(
                f"3MF-Objekt {instance.logical_object_id} besitzt keine AMS-Zuordnung"
            )
        name = instance.name or f"Part {order}"
        grouped_triangles: dict[int, list[tuple[int, int, int]]] = {}
        for triangle_index, triangle in enumerate(instance.triangles):
            material_index = instance.triangle_material_indices[triangle_index]
            if material_index is None:
                triangle_channel = channel
            else:
                triangle_channel = material_index + 1
                painted_triangle_count += 1
                painted_channels.add(triangle_channel)
            if triangle_channel is None:
                raise ValueError(
                    f"3MF-Objekt {instance.logical_object_id} besitzt keine AMS-Zuordnung"
                )
            if material_channel_count is not None and not 1 <= triangle_channel <= material_channel_count:
                raise ValueError(
                    "Eine bemalte 3MF-Fläche verweist auf keinen aktiven Materialkanal."
                )
            grouped_triangles.setdefault(int(triangle_channel), []).append(triangle)

        vertices = [
            (x + offset_x, y + offset_y, z)
            for x, y, z in instance.vertices
        ]
        for material_channel, triangles in sorted(grouped_triangles.items()):
            path = parts_dir / (
                f"part-{order:03d}-ch{material_channel}-{_safe_name(name)}.stl"
            )
            triangle_total += _write_binary_stl(path, name, vertices, triangles)
            manifest_objects.append(
                {
                    "path": str(path),
                    "count": 1,
                    "filaments": [material_channel],
                    "assemble_index": [1],
                    "pos_x": [0],
                    "pos_y": [0],
                    "pos_z": [0],
                }
            )
    return manifest_objects, triangle_total, {
        "painted_triangle_count": painted_triangle_count,
        "painted_material_channel_count": len(painted_channels),
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-root", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--process-source", required=True, type=Path)
    parser.add_argument("--process-output", required=True, type=Path)
    parser.add_argument("--manifest-output", required=True, type=Path)
    parser.add_argument("--parts-dir", required=True, type=Path)
    parser.add_argument("--summary-output", required=True, type=Path)
    args = parser.parse_args()

    job = _json(args.job)
    plan = job.get("material_plan")
    if not isinstance(plan, dict):
        raise ValueError("material_plan fehlt")
    filaments = plan.get("filaments")
    raw_assignments = plan.get("assignments")
    purge = (
        plan.get("purge_tower")
        if isinstance(plan.get("purge_tower"), dict)
        else {}
    )
    if not isinstance(filaments, list) or not filaments:
        raise ValueError("material_plan.filaments fehlt")
    if not isinstance(raw_assignments, dict):
        raise ValueError("material_plan.assignments fehlt")
    assignments = {
        str(key): int(value) for key, value in raw_assignments.items()
    }
    expected = set(range(1, len(filaments) + 1))
    if set(assignments.values()) - expected:
        raise ValueError(
            "material_plan enthält ungültige Materialkanäle"
        )

    target = (
        job.get("target_printer")
        if isinstance(job.get("target_printer"), dict)
        else {}
    )
    model = _canonical_model(target.get("model") or target.get("name"))
    process_dir = args.profile_root / "BBL" / "process"
    filament_dir = args.profile_root / "BBL" / "filament"
    overrides = (
        job.get("process_overrides")
        if isinstance(job.get("process_overrides"), dict)
        else {}
    )
    effective_overrides = dict(overrides)
    for key in ("min_layer_height_mm", "max_layer_height_mm"):
        if key not in effective_overrides and target.get(key) is not None:
            effective_overrides[key] = target.get(key)
    try:
        plate_index = max(0, int(job.get("requested_plate_index") or 0))
    except (TypeError, ValueError):
        plate_index = 0

    process, selected_paths, resolved, effective_tower, process_profile_proof = (
        _materialize_process(
            args.process_source,
            process_dir,
            filament_dir,
            [
                dict(item)
                for item in filaments
                if isinstance(item, dict)
            ],
            model,
            effective_overrides,
            purge,
            plate_index,
        )
    )
    args.process_output.parent.mkdir(parents=True, exist_ok=True)
    args.process_output.write_text(
        json.dumps(process, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    objects, triangles, paint_summary = _extract_parts(
        args.input,
        args.parts_dir,
        assignments,
        default_channel=1 if len(filaments) == 1 else None,
        material_channel_count=len(filaments),
        plate_width_mm=float(effective_overrides.get("build_plate_width_mm") or 256.0),
        plate_depth_mm=float(effective_overrides.get("build_plate_depth_mm") or 256.0),
    )
    layer_height_ranges = _validated_layer_height_ranges(effective_overrides)
    assembled_params = []
    if layer_height_ranges:
        assembled_params.append({
            "assemble_index": 1,
            "height_ranges": _native_height_ranges(layer_height_ranges),
        })
    manifest = {
        "plates": [
            {
                "plate_name": str(
                    job.get("studio_plate_name") or "V6 Druckplatte"
                ),
                "need_arrange": False,
                "plate_params": {
                    "filament_map_mode": "Manual",
                    "filament_map": " ".join("1" for _ in filaments),
                },
                "objects": objects,
            }
        ]
    }
    if assembled_params:
        manifest["plates"][0]["assembled_params"] = assembled_params
    args.manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = {
        "schema_version": 3,
        "model": model,
        "physical_extruder_count": int(
            target.get("physical_extruder_count") or 1
        ),
        "material_channel_count": len(filaments),
        "triangle_count": triangles,
        **paint_summary,
        "requested_plate_index": plate_index,
        "selected_process_profile": process_profile_proof,
        "variable_layer_heights": {
            "applied": bool(layer_height_ranges),
            "range_count": len(layer_height_ranges),
            "ranges": [
                {
                    "min_z_mm": item["min_z"],
                    "max_z_mm": item["max_z"],
                    "layer_height_mm": item["layer_height"],
                }
                for item in layer_height_ranges
            ],
            "native_scope": "assembled_model_group_1",
        },
        "process_settings": {
            key: process[key]
            for key in set((
                "layer_height",
                "outer_wall_speed",
                "inner_wall_speed",
                "enable_support",
                "support_type",
                "support_style",
                "support_on_build_plate_only",
                "support_threshold_angle",
                "v6_support_style",
            ))
            | set(_PROCESS_OVERRIDE_MAP.values())
            | set((overrides.get("selected_process_profile") or {}).get("settings", {}))
            if key in process
        },
        "purge_tower": {
            "enabled": (
                len(filaments) > 1
                and purge.get("enabled") is not False
            ),
            **effective_tower,
        },
        "filament_profile_paths": [
            str(path) for path in selected_paths
        ],
        "filaments": [
            {
                "channel": index + 1,
                "name": str(
                    profile.get("name") or selected_paths[index].stem
                ),
                "setting_id": str(profile.get("setting_id") or ""),
                "filament_id": str(
                    filaments[index].get("filament_id") or ""
                ),
                "color": str(filaments[index].get("color") or ""),
                "material": str(
                    filaments[index].get("material") or ""
                ),
                "ams_slot": filaments[index].get("display_slot"),
                "selected_profile_id": str(
                    (
                        filaments[index].get("selected_profile")
                        or {}
                    ).get("id")
                    or ""
                )
                if isinstance(
                    filaments[index].get("selected_profile"),
                    dict,
                )
                else "",
                "selected_profile_name": str(
                    (
                        filaments[index].get("selected_profile")
                        or {}
                    ).get("name")
                    or ""
                )
                if isinstance(
                    filaments[index].get("selected_profile"),
                    dict,
                )
                else "",
                "nozzle_temperature": _first(
                    profile.get("nozzle_temperature")
                ),
                "nozzle_temperature_initial_layer": _first(
                    profile.get("nozzle_temperature_initial_layer")
                ),
                "filament_flow_ratio": _first(
                    profile.get("filament_flow_ratio")
                ),
                "filament_max_volumetric_speed": _first(
                    profile.get("filament_max_volumetric_speed")
                ),
            }
            for index, profile in enumerate(resolved)
        ],
    }
    args.summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()