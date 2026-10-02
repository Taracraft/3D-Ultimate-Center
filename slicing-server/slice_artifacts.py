"""Slice artifact and G-code metadata types."""

from dataclasses import dataclass
from enum import StrEnum


class SliceArtifactKind(StrEnum):
    SLICED_3MF = "sliced_3mf"
    GCODE = "gcode"
    BGCODE = "bgcode"
    PREVIEW = "preview"
    LOG = "log"


@dataclass(slots=True, frozen=True)
class SliceArtifactRecord:
    id: str
    slice_job_id: str
    asset_id: str
    kind: SliceArtifactKind
    created_at: str


@dataclass(slots=True, frozen=True)
class GCodeLayer:
    layer_index: int
    z_height: float | None
    time_seconds: float | None
    filament_mm: float | None
    move_count: int
    extrusion_count: int
    travel_count: int


@dataclass(slots=True, frozen=True)
class GCodeMetadata:
    layer_count: int
    estimated_time_seconds: float | None
    filament_mm: float | None
    filament_grams: float | None
    filament_cost: float | None
    bounds: tuple[float, float, float, float, float, float] | None
    layers: tuple[GCodeLayer, ...]