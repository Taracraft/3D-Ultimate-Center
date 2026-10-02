"""Mesh metadata and analysis contracts."""

from dataclasses import dataclass

from .studio import Bounds3D, Vector3


@dataclass(slots=True, frozen=True)
class MeshFace:
    normal: Vector3
    area: float
    centroid: Vector3


@dataclass(slots=True, frozen=True)
class MeshMetadata:
    triangle_count: int
    vertex_count: int
    bounds: Bounds3D
    volume_mm3: float | None
    manifold: bool | None
    watertight: bool | None
    candidate_faces: tuple[MeshFace, ...] = ()


@dataclass(slots=True, frozen=True)
class FlatPlacement:
    rotation: tuple[float, float, float]
    support_area: float
    normal: Vector3
    confidence: float