"""Detailed material, feature, time and purge-tower analysis for Bambu G-code."""
from __future__ import annotations

from io import BytesIO
import json
import math
import re
from typing import Any, Iterable
import zipfile

_SETTING = re.compile(r"^;\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$")
_FEATURE = re.compile(r"^;\s*(?:FEATURE|TYPE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
_LAYER_Z = re.compile(
    r"(?:^|;)\s*(?:layer_z|Z_HEIGHT)\s*[:=]\s*([0-9.+-]+)",
    re.IGNORECASE,
)
_LAYER_NUMBER = re.compile(r"^;\s*LAYER\s*:\s*(-?\d+)", re.IGNORECASE)
_LAYER_TOTAL = re.compile(
    r"layer\s+num/total_layer_count:\s*\d+\s*/\s*(\d+)",
    re.IGNORECASE,
)
_COORD = re.compile(
    r"(?:^|\s)([XYZEFIJKP])(-?(?:\d+(?:\.\d*)?|\.\d+))",
    re.IGNORECASE,
)
_TOOL = re.compile(r"^T(\d+)$", re.IGNORECASE)
_M620 = re.compile(r"^M620\s+S(\d+)A", re.IGNORECASE)
_TOTAL_VALUE = re.compile(
    r"^;\s*total\s+filament\s+"
    r"(length\s*\[mm\]|volume\s*\[cm\^3\]|weight\s*\[g\])"
    r"\s*:\s*(.*?)\s*$",
    re.IGNORECASE,
)
_TOTAL_TIME = re.compile(r"total estimated time:\s*([^;\r\n]+)", re.IGNORECASE)
_MODEL_TIME = re.compile(r"model printing time:\s*([^;\r\n]+)", re.IGNORECASE)
_PRINT_END_MARKERS = (
    "; MACHINE_END_GCODE_START",
    "; EXECUTABLE_BLOCK_END",
)
_MAX_MATERIAL_CHANNELS = 32
_DENSITY_FALLBACK_G_CM3 = {
    "PLA": 1.24,
    "PLA-CF": 1.30,
    "PETG": 1.27,
    "PETG-CF": 1.30,
    "ABS": 1.04,
    "ASA": 1.07,
    "TPU": 1.21,
    "PA": 1.14,
    "PA-CF": 1.20,
    "PC": 1.20,
    "PVA": 1.23,
    "HIPS": 1.04,
}


def extract_gcode(data: bytes) -> bytes:
    """Return plain G-code from either raw data or a G-code 3MF."""
    if data[:2] != b"PK":
        return data
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            candidates = sorted(
                name
                for name in archive.namelist()
                if name.casefold().endswith(".gcode")
            )
            if not candidates:
                raise ValueError("G-Code-3MF enthält keine G-Code-Datei")
            return archive.read(candidates[0])
    except zipfile.BadZipFile as exc:
        raise ValueError("G-Code-3MF ist ungültig") from exc


def _setting_values(value: str) -> list[str]:
    raw = value.strip()
    if not raw:
        return []
    try:
        decoded = json.loads(raw)
        if isinstance(decoded, list):
            return [
                str(item).strip()
                for item in decoded
                if str(item).strip()
            ]
        if isinstance(decoded, str):
            raw = decoded
    except json.JSONDecodeError:
        raw = raw.strip('"')
    return [
        item.strip().strip('"')
        for item in re.split(r"[;,]", raw)
        if item.strip().strip('"')
    ]


def extract_gcode_settings(
    data: bytes,
    keys: Iterable[str],
) -> dict[str, list[str]]:
    """Extract only explicitly requested slicer settings from G-code comments."""
    requested = {
        str(key).strip().casefold()
        for key in keys
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", str(key).strip())
    }
    if not requested:
        return {}
    text = extract_gcode(data).decode("utf-8", errors="replace")
    result: dict[str, list[str]] = {}
    for raw in text.splitlines():
        setting = _SETTING.match(raw)
        if not setting:
            continue
        key = setting.group(1).casefold()
        if key in requested:
            result[key] = _setting_values(setting.group(2))
    return result


def extract_heater_commands(data: bytes) -> list[dict[str, Any]]:
    """Record executable thermal setpoints with their logical material channel."""
    channel = None
    result = []
    for raw in extract_gcode(data).decode("utf-8", errors="replace").splitlines():
        command = raw.split(";", 1)[0].strip().upper()
        tool = re.fullmatch(r"T(\d+)", command)
        if tool:
            value = int(tool[1])
            if value < _MAX_MATERIAL_CHANNELS:
                channel = value + 1
            elif value == 255:
                channel = None  # Unload; T1000 preserves the selected filament.
        heater = re.match(r"^(M104|M109|M140|M190)\s+.*?[SR](-?(?:\d+(?:\.\d*)?|\.\d+))(?:\s|$)", command)
        if heater:
            result.append({"command": heater[1], "temperature_c": float(heater[2]),
                           "channel": channel if heater[1] in {"M104", "M109"} else None})
    return result


def _float_values(values: list[str]) -> list[float]:
    result: list[float] = []
    for value in values:
        try:
            result.append(float(value))
        except (TypeError, ValueError):
            result.append(0.0)
    return result


def _value_at(values: list[Any], index: int, fallback: Any) -> Any:
    if 0 <= index < len(values):
        return values[index]
    if values:
        return values[0]
    return fallback


def _duration_seconds(value: str | None) -> int | None:
    if not value:
        return None
    days = re.search(r"(\d+)\s*d", value, re.IGNORECASE)
    hours = re.search(r"(\d+)\s*h", value, re.IGNORECASE)
    minutes = re.search(r"(\d+)\s*m", value, re.IGNORECASE)
    seconds = re.search(r"(\d+)\s*s", value, re.IGNORECASE)
    if not any((days, hours, minutes, seconds)):
        return None
    return (
        (int(days.group(1)) if days else 0) * 86400
        + (int(hours.group(1)) if hours else 0) * 3600
        + (int(minutes.group(1)) if minutes else 0) * 60
        + (int(seconds.group(1)) if seconds else 0)
    )


def _normalise_material(value: object) -> str:
    material = str(value or "").strip().upper().replace(" ", "-")
    if material.startswith("GENERIC-"):
        material = material.removeprefix("GENERIC-")
    return material or "UNKNOWN"


def _feature_key(label: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", label.casefold()).strip()
    exact = {
        "inner wall": "inner_wall",
        "outer wall": "outer_wall",
        "sparse infill": "sparse_infill",
        "internal solid infill": "internal_solid_infill",
        "top surface": "top_surface",
        "bottom surface": "bottom_surface",
        "gap infill": "gap_infill",
        "support": "support",
        "support interface": "support_interface",
        "brim": "brim",
        "raft": "raft",
        "skirt": "skirt",
        "prime tower": "prime_tower",
        "wipe tower": "prime_tower",
        "purge tower": "prime_tower",
        "bridge": "bridge",
        "overhang wall": "overhang_wall",
    }
    if value in exact:
        return exact[value]
    if "support interface" in value:
        return "support_interface"
    if "support" in value:
        return "support"
    if "tower" in value and any(
        word in value for word in ("prime", "wipe", "purge")
    ):
        return "prime_tower"
    for key in ("brim", "raft", "skirt"):
        if key in value:
            return key
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_") or "other"


def _feature_category(key: str) -> str:
    if key in {"support", "support_interface"}:
        return "support"
    if key in {"brim", "raft", "skirt"}:
        return "adhesion"
    if key == "prime_tower":
        return "purge_tower"
    if key == "flush_waste":
        return "waste"
    return "model"


def _filament_grams(
    length_mm: float,
    diameter_mm: float,
    density_g_cm3: float,
) -> float:
    if min(length_mm, diameter_mm, density_g_cm3) <= 0:
        return 0.0
    volume_mm3 = length_mm * math.pi * (diameter_mm / 2.0) ** 2
    return volume_mm3 / 1000.0 * density_g_cm3


def _motion_seconds(
    x: float,
    y: float,
    z: float,
    e: float,
    nx: float,
    ny: float,
    nz: float,
    ne: float,
    feed_mm_min: float,
) -> float:
    if feed_mm_min <= 0:
        return 0.0
    spatial = math.sqrt(
        (nx - x) ** 2 + (ny - y) ** 2 + (nz - z) ** 2
    )
    distance = spatial if spatial > 0.000001 else abs(ne - e)
    return distance / feed_mm_min * 60.0


def analyze_gcode(
    data: bytes,
    *,
    plate_width_mm: float = 256.0,
    plate_depth_mm: float = 256.0,
) -> dict[str, Any]:
    """Analyze rendered G-code by AMS channel, feature, time and tower geometry."""
    text = extract_gcode(data).decode("utf-8", errors="ignore")
    settings: dict[str, list[str]] = {}
    header_totals: dict[str, list[float]] = {}
    total_time_seconds: int | None = None
    model_time_seconds: int | None = None
    layer_count = 0

    for raw in text.splitlines():
        setting = _SETTING.match(raw)
        if setting:
            settings[setting.group(1).casefold()] = _setting_values(
                setting.group(2)
            )
        total = _TOTAL_VALUE.match(raw)
        if total:
            header_totals[total.group(1).casefold()] = _float_values(
                _setting_values(total.group(2))
            )
        if total_time_seconds is None:
            match = _TOTAL_TIME.search(raw)
            if match:
                total_time_seconds = _duration_seconds(match.group(1))
        if model_time_seconds is None:
            match = _MODEL_TIME.search(raw)
            if match:
                model_time_seconds = _duration_seconds(match.group(1))
        layer = _LAYER_TOTAL.search(raw)
        if layer:
            layer_count = max(layer_count, int(layer.group(1)))

    if not layer_count:
        try:
            layer_count = int(
                float(_value_at(settings.get("total_layer_number", []), 0, 0))
            )
        except (TypeError, ValueError):
            layer_count = 0

    colors = settings.get("filament_colour", [])
    names = settings.get("filament_settings_id", [])
    materials = settings.get("filament_type", [])
    diameters = _float_values(settings.get("filament_diameter", []))
    densities = _float_values(settings.get("filament_density", []))
    filament_ids = settings.get("filament_ids", [])

    x = y = z = e = feed = 0.0
    absolute_xyz = True
    absolute_e = True
    pending_tool = 0
    last_used_tool: int | None = None
    material_changes = 0
    feature_label = "Other"
    feature_key = "other"
    capture = False
    has_explicit_z = bool(_LAYER_Z.search(text))
    in_flush = False
    in_wipe_tower = False

    raw_usage: dict[int, dict[str, dict[str, float]]] = {}
    feature_labels: dict[str, str] = {}
    feature_motion_seconds: dict[str, float] = {}
    feature_move_counts: dict[str, int] = {}
    tower_bounds = {
        "min_x": math.inf,
        "min_y": math.inf,
        "max_x": -math.inf,
        "max_y": -math.inf,
    }
    tower_extrusion_moves = 0

    for raw in text.splitlines():
        stripped = raw.strip()
        upper_raw = stripped.upper()
        if any(upper_raw.startswith(marker) for marker in _PRINT_END_MARKERS):
            break

        if upper_raw.startswith("; FLUSH_START"):
            in_flush = True
        elif upper_raw.startswith("; FLUSH_END"):
            in_flush = False
        elif upper_raw.startswith("; WIPE_TOWER_START"):
            in_wipe_tower = True
        elif upper_raw.startswith("; WIPE_TOWER_END"):
            in_wipe_tower = False

        feature_match = _FEATURE.match(stripped)
        if feature_match:
            feature_label = feature_match.group(1).strip() or "Other"
            feature_key = _feature_key(feature_label)
            feature_labels.setdefault(feature_key, feature_label)

        if _LAYER_Z.search(raw) or (
            not has_explicit_z and _LAYER_NUMBER.match(stripped)
        ):
            capture = True

        command = raw.split(";", 1)[0].strip()
        if not command:
            continue
        upper = command.upper()
        if upper == "G90":
            absolute_xyz = True
            continue
        if upper == "G91":
            absolute_xyz = False
            continue
        if upper == "M82":
            absolute_e = True
            continue
        if upper == "M83":
            absolute_e = False
            continue

        tool_match = _TOOL.match(upper) or _M620.match(upper)
        if tool_match:
            selected = int(tool_match.group(1))
            if 0 <= selected < _MAX_MATERIAL_CHANNELS:
                pending_tool = selected
            continue

        values = {
            axis.upper(): float(value)
            for axis, value in _COORD.findall(command)
        }
        if upper.startswith("G92"):
            x = values.get("X", x)
            y = values.get("Y", y)
            z = values.get("Z", z)
            e = values.get("E", e)
            continue

        code = upper.split(maxsplit=1)[0]
        if code not in {
            "G0",
            "G00",
            "G1",
            "G01",
            "G2",
            "G02",
            "G3",
            "G03",
        }:
            continue
        feed = values.get("F", feed)
        nx = values.get("X", x if absolute_xyz else 0.0)
        ny = values.get("Y", y if absolute_xyz else 0.0)
        nz = values.get("Z", z if absolute_xyz else 0.0)
        raw_e = values.get("E", e if absolute_e else 0.0)
        if not absolute_xyz:
            nx += x
            ny += y
            nz += z
        ne = raw_e if absolute_e else e + raw_e
        extrusion = ne - e if absolute_e else raw_e
        time_key = "flush_waste" if in_flush else feature_key
        if in_flush:
            feature_labels.setdefault("flush_waste", "Spülabfall")

        if capture:
            elapsed = _motion_seconds(
                x,
                y,
                z,
                e,
                nx,
                ny,
                nz,
                ne,
                feed,
            )
            if elapsed > 0:
                feature_motion_seconds[time_key] = (
                    feature_motion_seconds.get(time_key, 0.0) + elapsed
                )
                feature_move_counts[time_key] = (
                    feature_move_counts.get(time_key, 0) + 1
                )

        if (
            capture
            and extrusion > 0
            and 0 <= pending_tool < _MAX_MATERIAL_CHANNELS
        ):
            if last_used_tool is None:
                last_used_tool = pending_tool
            elif pending_tool != last_used_tool:
                material_changes += 1
                last_used_tool = pending_tool

            usage = raw_usage.setdefault(pending_tool, {}).setdefault(
                time_key,
                {"extrusion_mm": 0.0, "move_count": 0.0},
            )
            usage["extrusion_mm"] += extrusion
            usage["move_count"] += 1

            spatial_xy = math.hypot(nx - x, ny - y)
            if (
                in_wipe_tower
                and not in_flush
                and spatial_xy > 0.000001
            ):
                tower_extrusion_moves += 1
                tower_bounds["min_x"] = min(tower_bounds["min_x"], x, nx)
                tower_bounds["min_y"] = min(tower_bounds["min_y"], y, ny)
                tower_bounds["max_x"] = max(tower_bounds["max_x"], x, nx)
                tower_bounds["max_y"] = max(tower_bounds["max_y"], y, ny)

        x, y, z, e = nx, ny, nz, ne

    channel_count = max(
        len(colors),
        len(names),
        len(materials),
        len(diameters),
        len(densities),
        len(filament_ids),
        max(raw_usage, default=-1) + 1,
        1,
    )
    tools = list(range(channel_count))
    header_lengths = header_totals.get("length [mm]", [])
    header_volumes = header_totals.get("volume [cm^3]", [])
    header_weights = header_totals.get("weight [g]", [])

    raw_time_total = sum(feature_motion_seconds.values())
    time_scale = (
        model_time_seconds / raw_time_total
        if model_time_seconds and raw_time_total > 0
        else 1.0
    )
    scaled_times = {
        key: value * time_scale
        for key, value in feature_motion_seconds.items()
    }
    preparation_seconds = (
        max(0, total_time_seconds - model_time_seconds)
        if total_time_seconds is not None
        and model_time_seconds is not None
        else None
    )
    expected_total_seconds = (
        model_time_seconds + preparation_seconds
        if model_time_seconds is not None
        and preparation_seconds is not None
        else None
    )
    time_delta_seconds = (
        total_time_seconds - expected_total_seconds
        if total_time_seconds is not None
        and expected_total_seconds is not None
        else None
    )
    excessive_preparation = (
        preparation_seconds is not None
        and model_time_seconds is not None
        and preparation_seconds > max(1800, int(model_time_seconds * 0.05))
    )
    raw_motion_mismatch = (
        raw_time_total > 0
        and model_time_seconds is not None
        and abs(raw_time_total - model_time_seconds)
        > max(1800, int(model_time_seconds * 0.35))
    )
    time_consistency = {
        "status": "missing"
        if total_time_seconds is None or model_time_seconds is None
        else "mismatch"
        if excessive_preparation or raw_motion_mismatch
        else "ok",
        "source": "bambu_gcode_header",
        "expected_total_seconds": expected_total_seconds,
        "delta_seconds": time_delta_seconds,
        "raw_motion_seconds": round(raw_time_total),
        "note": (
            "G-Code-Zeit wirkt unplausibel: Gesamt-, Modell- und Bewegungszeit bitte mit Bambu Studio gegenprüfen."
            if excessive_preparation or raw_motion_mismatch
            else ""
        ),
    }

    channels: list[dict[str, Any]] = []
    feature_totals: dict[str, dict[str, Any]] = {}
    total_length = total_volume = total_weight = 0.0
    estimated_material_values = False

    for position, tool_index in enumerate(tools):
        raw_features = raw_usage.get(tool_index, {})
        parsed_length = sum(
            item["extrusion_mm"] for item in raw_features.values()
        )
        header_length = float(_value_at(header_lengths, position, 0.0))
        length_mm = (
            header_length
            if header_length > 0
            and len(header_lengths) in {1, channel_count}
            else parsed_length
        )
        diameter = float(_value_at(diameters, tool_index, 1.75) or 1.75)
        material = _normalise_material(
            _value_at(materials, tool_index, "UNKNOWN")
        )
        density = float(_value_at(densities, tool_index, 0.0) or 0.0)
        density_source = "gcode"
        if density <= 0:
            density = _DENSITY_FALLBACK_G_CM3.get(material, 0.0)
            density_source = (
                "material_fallback" if density > 0 else "unavailable"
            )

        header_weight = float(_value_at(header_weights, position, 0.0))
        if header_weight > 0 and len(header_weights) in {1, channel_count}:
            weight_g = header_weight
            weight_source = "gcode_total"
        else:
            weight_g = _filament_grams(length_mm, diameter, density)
            weight_source = (
                "calculated"
                if density_source == "gcode"
                else "estimated"
                if density > 0
                else "unavailable"
            )
        estimated_material_values = (
            estimated_material_values
            or weight_source in {"estimated", "unavailable"}
        )

        calculated_volume = (
            length_mm * math.pi * (diameter / 2.0) ** 2 / 1000.0
        )
        header_volume = float(_value_at(header_volumes, position, 0.0))
        volume_cm3 = calculated_volume
        if header_volume > 0 and len(header_volumes) in {1, channel_count}:
            direct_error = abs(header_volume - calculated_volume)
            scaled_error = abs(header_volume / 1000.0 - calculated_volume)
            if direct_error <= max(0.05, calculated_volume * 0.2):
                volume_cm3 = header_volume
            elif scaled_error <= max(0.05, calculated_volume * 0.2):
                volume_cm3 = header_volume / 1000.0

        denominator = parsed_length or 1.0
        by_feature: dict[str, dict[str, Any]] = {}
        for key, raw_item in sorted(raw_features.items()):
            ratio = raw_item["extrusion_mm"] / denominator
            detail = {
                "key": key,
                "label": feature_labels.get(
                    key,
                    key.replace("_", " ").title(),
                ),
                "category": _feature_category(key),
                "length_mm": round(length_mm * ratio, 3),
                "volume_cm3": round(volume_cm3 * ratio, 4),
                "weight_g": round(weight_g * ratio, 4),
                "extrusion_move_count": int(raw_item["move_count"]),
            }
            by_feature[key] = detail
            aggregate = feature_totals.setdefault(
                key,
                {
                    "key": key,
                    "label": detail["label"],
                    "category": detail["category"],
                    "length_mm": 0.0,
                    "volume_cm3": 0.0,
                    "weight_g": 0.0,
                    "extrusion_move_count": 0,
                    "materials": [],
                },
            )
            for metric in ("length_mm", "volume_cm3", "weight_g"):
                aggregate[metric] += detail[metric]
            aggregate["extrusion_move_count"] += detail[
                "extrusion_move_count"
            ]
            aggregate["materials"].append(
                {
                    "material_channel_number": tool_index + 1,
                    "length_mm": detail["length_mm"],
                    "weight_g": detail["weight_g"],
                }
            )

        channels.append(
            {
                "slicer_tool_index": tool_index,
                "material_channel_number": tool_index + 1,
                "name": str(
                    _value_at(
                        names,
                        tool_index,
                        f"Filament {tool_index + 1}",
                    )
                ),
                "material": material,
                "color": str(
                    _value_at(colors, tool_index, "#50DB6C")
                ),
                "filament_id": str(
                    _value_at(filament_ids, tool_index, "")
                ),
                "diameter_mm": round(diameter, 4),
                "density_g_cm3": round(density, 4) if density > 0 else None,
                "density_source": density_source,
                "length_mm": round(length_mm, 3),
                "volume_cm3": round(volume_cm3, 4),
                "weight_g": round(weight_g, 4),
                "weight_source": weight_source,
                "features": by_feature,
            }
        )
        total_length += length_mm
        total_volume += volume_cm3
        total_weight += weight_g

    features: list[dict[str, Any]] = []
    for key, item in feature_totals.items():
        item.update(
            {
                "time_seconds": round(scaled_times.get(key, 0.0)),
                "time_estimated": True,
                "motion_move_count": feature_move_counts.get(key, 0),
                "length_mm": round(item["length_mm"], 3),
                "volume_cm3": round(item["volume_cm3"], 4),
                "weight_g": round(item["weight_g"], 4),
            }
        )
        features.append(item)
    features.sort(
        key=lambda item: (
            -item["time_seconds"],
            -item["weight_g"],
            item["label"],
        )
    )

    if tower_extrusion_moves:
        bounds = {
            key: round(float(value), 4)
            for key, value in tower_bounds.items()
        }
        tolerance = 0.05
        inside_plate = (
            tower_bounds["min_x"] >= -tolerance
            and tower_bounds["min_y"] >= -tolerance
            and tower_bounds["max_x"] <= plate_width_mm + tolerance
            and tower_bounds["max_y"] <= plate_depth_mm + tolerance
        )
        tower_safety = {
            "present": True,
            "extrusion_move_count": tower_extrusion_moves,
            "bounds": bounds,
            "inside_plate": inside_plate,
            "source": (
                "räumliche Extrusionslinien innerhalb WIPE_TOWER, ohne FLUSH"
            ),
        }
    else:
        tower_safety = {
            "present": False,
            "extrusion_move_count": 0,
            "bounds": None,
            "inside_plate": True,
            "source": (
                "räumliche Extrusionslinien innerhalb WIPE_TOWER, ohne FLUSH"
            ),
        }

    # Calculate support/bridge warnings
    support_seconds = feature_motion_seconds.get("support", 0.0) + feature_motion_seconds.get("support_interface", 0.0)
    bridge_seconds = feature_motion_seconds.get("bridge", 0.0)
    warnings: list[str] = []
    if bridge_seconds > 0 and support_seconds <= 0:
        warnings.append("Brücken ohne Stützstruktur erkannt - Druckfehler möglich")
    return {
        "schema_version": 4,
        "time": {
            "total_seconds": total_time_seconds,
            "model_seconds": model_time_seconds,
            "preparation_seconds": preparation_seconds,
            "consistency": time_consistency,
            "feature_time_method": (
                "G-Code-Bewegungszeiten, auf die Bambu-Modellzeit skaliert"
            ),
            "feature_time_estimated": True,
        },
        "layer_count": layer_count or None,
        "physical_extruder_count": 1,
        "material_channel_count": len(channels),
        "filament_change_count": material_changes,
        "materials": channels,
        "features": features,
        "totals": {
            "length_mm": round(total_length, 3),
            "volume_cm3": round(total_volume, 4),
            "weight_g": round(total_weight, 4),
        },
        "tower_safety": tower_safety,
        "estimated_material_values": estimated_material_values,
    }


def assert_prime_tower_inside(analysis: dict[str, Any]) -> None:
    """Reject a rendered artifact whose physical tower paths leave the plate."""
    tower = analysis.get("tower_safety")
    if not isinstance(tower, dict) or not tower.get("present"):
        return
    if tower.get("inside_plate") is not True:
        raise ValueError(
            "Der geslicte Reinigungsturm liegt außerhalb der Druckplatte: "
            f"{tower.get('bounds')}"
        )
