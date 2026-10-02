"""Parse real G-code extrusion paths into stable, feature-aware preview data."""
from __future__ import annotations

from io import BytesIO
import json
import math
import re
import zipfile

_LAYER_Z = re.compile(r"(?:^|;)\s*(?:layer_z|Z_HEIGHT)\s*[:=]\s*([0-9.+-]+)", re.IGNORECASE)
_LAYER_NUMBER = re.compile(r"^;\s*LAYER\s*:\s*(-?\d+)", re.IGNORECASE)
_FEATURE = re.compile(r"^;\s*(?:FEATURE|TYPE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
_COORD = re.compile(r"(?:^|\s)([XYZEFIJKP])(-?(?:\d+(?:\.\d*)?|\.\d+))", re.IGNORECASE)
_TOOL = re.compile(r"^T(\d+)$", re.IGNORECASE)
_M620 = re.compile(r"^M620\s+S(\d+)A", re.IGNORECASE)
_SETTING = re.compile(r"^;\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$")
_PRINT_END_MARKERS = (
    "; MACHINE_END_GCODE_START",
    "; EXECUTABLE_BLOCK_END",
)


def extract_gcode(data: bytes) -> bytes:
    if data[:2] != b"PK":
        return data
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            candidates = [name for name in archive.namelist() if name.casefold().endswith(".gcode")]
            if not candidates:
                raise ValueError("G-Code-3MF enthält keine G-Code-Datei")
            return archive.read(sorted(candidates)[0])
    except zipfile.BadZipFile as exc:
        raise ValueError("G-Code-3MF ist ungültig") from exc


def _setting_values(value: str) -> list[str]:
    raw = value.strip()
    if not raw:
        return []
    try:
        decoded = json.loads(raw)
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
        if isinstance(decoded, str):
            raw = decoded
    except json.JSONDecodeError:
        raw = raw.strip('"')
    return [item.strip().strip('"') for item in re.split(r"[;,]", raw) if item.strip().strip('"')]


def _metadata(text: str) -> tuple[list[str], list[str]]:
    colors: list[str] = []
    names: list[str] = []
    fallback_color = ""
    for raw in text.splitlines():
        match = _SETTING.match(raw)
        if not match:
            continue
        key = match.group(1).casefold()
        values = _setting_values(match.group(2))
        if key == "filament_colour" and values:
            colors = values
        elif key == "filament_settings_id" and values:
            names = values
        elif key == "extruder_colour" and values:
            fallback_color = values[0]
    if not colors and fallback_color:
        colors = [fallback_color]
    normalized = []
    for value in colors:
        color = value.strip().upper()
        if not color.startswith("#"):
            color = f"#{color}"
        if re.fullmatch(r"#[0-9A-F]{8}", color):
            color = color[:7]
        normalized.append(color if re.fullmatch(r"#[0-9A-F]{6}", color) else "#50DB6C")
    return normalized, names


def _feature_category(feature: str) -> str:
    value = feature.casefold().replace("_", " ")
    if "support" in value:
        return "support"
    if "brim" in value:
        return "brim"
    if "raft" in value:
        return "raft"
    if "skirt" in value:
        return "skirt"
    if any(token in value for token in ("prime tower", "wipe tower", "purge tower", "prime-tower", "wipe-tower")):
        return "purge_tower"
    return "model"


def _arc_points(
    x: float,
    y: float,
    nx: float,
    ny: float,
    values: dict[str, float],
    clockwise: bool,
) -> list[tuple[float, float]]:
    if "I" not in values and "J" not in values:
        return [(nx, ny)]
    cx = x + values.get("I", 0.0)
    cy = y + values.get("J", 0.0)
    radius = math.hypot(x - cx, y - cy)
    if radius <= 1e-6:
        return [(nx, ny)]
    start = math.atan2(y - cy, x - cx)
    finish = math.atan2(ny - cy, nx - cx)
    sweep = finish - start
    if clockwise:
        while sweep >= 0:
            sweep -= math.tau
    else:
        while sweep <= 0:
            sweep += math.tau
    turns = max(1, int(round(values.get("P", 1.0))))
    if turns > 1:
        sweep += (-math.tau if clockwise else math.tau) * (turns - 1)
    steps = max(4, min(180, int(math.ceil(abs(sweep) * radius / 1.5))))
    return [
        (
            cx + math.cos(start + sweep * step / steps) * radius,
            cy + math.sin(start + sweep * step / steps) * radius,
        )
        for step in range(1, steps + 1)
    ]


def _parsed_layers(data: bytes) -> tuple[list[dict[str, object]], dict[str, object]]:
    text = extract_gcode(data).decode("utf-8", errors="ignore")
    filament_colors, filament_names = _metadata(text)
    has_explicit_z = bool(_LAYER_Z.search(text))
    layers: list[dict[str, object]] = []
    x = y = z = e = 0.0
    absolute_xyz = True
    absolute_e = True
    tool = 0
    feature = "Modell"
    capture = False
    current_layer: dict[str, object] | None = None
    bounds = {
        "min_x": math.inf,
        "min_y": math.inf,
        "min_z": math.inf,
        "max_x": -math.inf,
        "max_y": -math.inf,
        "max_z": -math.inf,
    }
    feature_first_layers: dict[str, int] = {}

    def begin_layer(layer_z: float) -> None:
        nonlocal current_layer, capture, z
        capture = True
        z = layer_z
        current_layer = {
            "index": len(layers),
            "z": round(layer_z, 5),
            "segments": [],
            "extrusion_mm": 0.0,
            "features": [],
        }
        layers.append(current_layer)

    def add_segment(x1: float, y1: float, x2: float, y2: float, extrusion: float) -> None:
        if current_layer is None or extrusion <= 0 or math.hypot(x2 - x1, y2 - y1) <= 0.0001:
            return
        category = _feature_category(feature)
        segment = [
            round(x1, 4),
            round(y1, 4),
            round(x2, 4),
            round(y2, 4),
            round(float(current_layer["z"]), 5),
            tool,
            round(extrusion, 5),
            feature,
            category,
        ]
        segments = current_layer["segments"]
        assert isinstance(segments, list)
        segments.append(segment)
        current_layer["extrusion_mm"] = round(float(current_layer["extrusion_mm"]) + extrusion, 5)
        features = current_layer["features"]
        assert isinstance(features, list)
        if feature not in features:
            features.append(feature)
        feature_first_layers.setdefault(category, int(current_layer["index"]))
        bounds["min_x"] = min(bounds["min_x"], x1, x2)
        bounds["min_y"] = min(bounds["min_y"], y1, y2)
        bounds["min_z"] = min(bounds["min_z"], float(current_layer["z"]))
        bounds["max_x"] = max(bounds["max_x"], x1, x2)
        bounds["max_y"] = max(bounds["max_y"], y1, y2)
        bounds["max_z"] = max(bounds["max_z"], float(current_layer["z"]))

    for raw in text.splitlines():
        stripped = raw.strip()
        upper_raw = stripped.upper()
        if any(upper_raw.startswith(marker) for marker in _PRINT_END_MARKERS):
            break

        feature_match = _FEATURE.match(stripped)
        if feature_match:
            feature = feature_match.group(1).strip() or "Modell"

        marker = _LAYER_Z.search(raw)
        if marker:
            try:
                begin_layer(float(marker.group(1)))
            except ValueError:
                pass
        elif not has_explicit_z and _LAYER_NUMBER.match(stripped):
            begin_layer(z)

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

        match = _TOOL.match(upper) or _M620.match(upper)
        if match:
            selected = int(match.group(1))
            if selected < 255:
                tool = max(0, selected)
            continue

        if upper.startswith("G92"):
            values = {axis.upper(): float(value) for axis, value in _COORD.findall(command)}
            if "X" in values:
                x = values["X"]
            if "Y" in values:
                y = values["Y"]
            if "Z" in values:
                z = values["Z"]
            if "E" in values:
                e = values["E"]
            continue

        code = upper.split(maxsplit=1)[0]
        if code not in {"G0", "G00", "G1", "G01", "G2", "G02", "G3", "G03"}:
            continue
        values = {axis.upper(): float(value) for axis, value in _COORD.findall(command)}
        nx = values.get("X", x if absolute_xyz else 0.0)
        ny = values.get("Y", y if absolute_xyz else 0.0)
        nz = values.get("Z", z if absolute_xyz else 0.0)
        ne = values.get("E", e if absolute_e else 0.0)
        if not absolute_xyz:
            nx += x
            ny += y
            nz += z
        if absolute_e:
            extrusion = ne - e
        else:
            extrusion = ne
            ne = e + ne

        if capture and extrusion > 0:
            if code in {"G2", "G02", "G3", "G03"}:
                points = _arc_points(x, y, nx, ny, values, code in {"G2", "G02"})
                previous_x, previous_y = x, y
                total_length = sum(
                    math.hypot(px - sx, py - sy)
                    for (sx, sy), (px, py) in zip([(x, y), *points[:-1]], points)
                ) or 1.0
                for point_x, point_y in points:
                    part_length = math.hypot(point_x - previous_x, point_y - previous_y)
                    add_segment(previous_x, previous_y, point_x, point_y, extrusion * part_length / total_length)
                    previous_x, previous_y = point_x, point_y
            else:
                add_segment(x, y, nx, ny, extrusion)
        x, y, z, e = nx, ny, nz, ne

    non_empty = [layer for layer in layers if layer["segments"]]
    for index, layer in enumerate(non_empty):
        layer["index"] = index
    valid_first: dict[str, int] = {}
    for category in feature_first_layers:
        for index, layer in enumerate(non_empty):
            segments = layer["segments"]
            if isinstance(segments, list) and any(len(item) > 8 and item[8] == category for item in segments):
                valid_first[category] = index
                break
    if not non_empty:
        normalized_bounds = {"min_x": 0.0, "min_y": 0.0, "min_z": 0.0, "max_x": 256.0, "max_y": 256.0, "max_z": 1.0}
    else:
        normalized_bounds = {key: round(float(value), 4) for key, value in bounds.items()}
    return non_empty, {
        "filament_colors": filament_colors,
        "filament_names": filament_names,
        "feature_first_layers": valid_first,
        "bounds": normalized_bounds,
    }


def parse_toolpath(
    data: bytes,
    selected_layer: int | None = None,
    start_layer: int | None = None,
    end_layer: int | None = None,
) -> dict[str, object]:
    layers, metadata = _parsed_layers(data)
    result: dict[str, object] = {
        "layer_count": len(layers),
        "layers": [
            {
                "index": layer["index"],
                "z": layer["z"],
                "segment_count": len(layer["segments"]),
                "extrusion_mm": layer["extrusion_mm"],
                "features": layer["features"],
            }
            for layer in layers
        ],
        "tools": sorted({int(segment[5]) for layer in layers for segment in layer["segments"]}),
        **metadata,
    }
    if selected_layer is not None:
        if selected_layer < 0 or selected_layer >= len(layers):
            raise ValueError("Layer liegt außerhalb des gültigen Bereichs")
        result["selected"] = layers[selected_layer]
    if start_layer is not None or end_layer is not None:
        start = max(0, int(start_layer or 0))
        end = min(len(layers), int(end_layer if end_layer is not None else start + 1))
        if start >= len(layers) or end <= start:
            raise ValueError("Layer-Bereich liegt außerhalb des gültigen Bereichs")
        result["chunk"] = {
            "start_layer": start,
            "end_layer": end,
            "layers": layers[start:end],
            "segment_count": sum(len(layer["segments"]) for layer in layers[start:end]),
        }
    return result
