"""Streaming G-code metadata parser for layer and movement statistics."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from .slice_artifacts import GCodeLayer, GCodeMetadata

_LAYER_RE = re.compile(r"^;\s*(?:LAYER|layer)\s*[:=]\s*(\d+)")
_TIME_RE = re.compile(r"^;\s*(?:TIME|estimated printing time)\s*[:=]\s*([0-9.]+)", re.I)
_FILAMENT_RE = re.compile(r"^;\s*filament used\s*[:=]\s*([0-9.]+)\s*(mm|m)?", re.I)


@dataclass(slots=True)
class _LayerAccumulator:
    index: int
    z_height: float | None = None
    move_count: int = 0
    extrusion_count: int = 0
    travel_count: int = 0
    filament_mm: float = 0.0

    def record_move(self, extruded: float, z_height: float | None) -> None:
        self.move_count += 1
        if z_height is not None:
            self.z_height = z_height
        if extruded > 0:
            self.extrusion_count += 1
            self.filament_mm += extruded
        else:
            self.travel_count += 1

    def build(self) -> GCodeLayer:
        return GCodeLayer(
            layer_index=self.index,
            z_height=self.z_height,
            time_seconds=None,
            filament_mm=self.filament_mm,
            move_count=self.move_count,
            extrusion_count=self.extrusion_count,
            travel_count=self.travel_count,
        )


def parse_gcode(path: str | Path) -> GCodeMetadata:
    source = Path(path)
    layers: list[GCodeLayer] = []
    current = _LayerAccumulator(0)
    explicit_layer_seen = False
    absolute_extrusion = True
    last_e = 0.0
    current_z: float | None = None
    estimated_time_seconds: float | None = None
    declared_filament_mm: float | None = None
    min_x = min_y = min_z = math.inf
    max_x = max_y = max_z = -math.inf

    with source.open("r", encoding="utf-8", errors="ignore") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue

            layer_match = _LAYER_RE.match(line)
            if layer_match:
                if explicit_layer_seen or current.move_count:
                    layers.append(current.build())
                current = _LayerAccumulator(int(layer_match.group(1)))
                explicit_layer_seen = True
                continue

            time_match = _TIME_RE.match(line)
            if time_match:
                estimated_time_seconds = float(time_match.group(1))
                continue

            filament_match = _FILAMENT_RE.match(line)
            if filament_match:
                value = float(filament_match.group(1))
                unit = (filament_match.group(2) or "mm").casefold()
                declared_filament_mm = value * 1000.0 if unit == "m" else value
                continue

            code = line.split(";", 1)[0].strip()
            if not code:
                continue
            upper = code.upper()
            if upper.startswith("M82"):
                absolute_extrusion = True
                continue
            if upper.startswith("M83"):
                absolute_extrusion = False
                continue
            if upper.startswith("G92"):
                values = _parse_axes(code)
                if "E" in values:
                    last_e = values["E"]
                continue
            if not (upper.startswith("G0") or upper.startswith("G1")):
                continue

            values = _parse_axes(code)
            if "Z" in values:
                current_z = values["Z"]
            extruded = 0.0
            if "E" in values:
                e_value = values["E"]
                if absolute_extrusion:
                    extruded = max(0.0, e_value - last_e)
                    last_e = e_value
                else:
                    extruded = max(0.0, e_value)

            if "X" in values:
                min_x = min(min_x, values["X"])
                max_x = max(max_x, values["X"])
            if "Y" in values:
                min_y = min(min_y, values["Y"])
                max_y = max(max_y, values["Y"])
            if current_z is not None:
                min_z = min(min_z, current_z)
                max_z = max(max_z, current_z)

            current.record_move(extruded, current_z)

    if current.move_count or not layers:
        layers.append(current.build())

    calculated_filament = sum(layer.filament_mm or 0.0 for layer in layers)
    filament_mm = declared_filament_mm if declared_filament_mm is not None else calculated_filament
    bounds = None
    if all(math.isfinite(value) for value in (min_x, min_y, min_z, max_x, max_y, max_z)):
        bounds = (min_x, min_y, min_z, max_x, max_y, max_z)

    return GCodeMetadata(
        layer_count=len(layers),
        estimated_time_seconds=estimated_time_seconds,
        filament_mm=filament_mm,
        filament_grams=None,
        filament_cost=None,
        bounds=bounds,
        layers=tuple(layers),
    )


def _parse_axes(code: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for token in code.split()[1:]:
        if len(token) < 2:
            continue
        axis = token[0].upper()
        if axis not in {"X", "Y", "Z", "E", "F"}:
            continue
        try:
            values[axis] = float(token[1:])
        except ValueError:
            continue
    return values
