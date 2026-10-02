"""Geometry-only mesh analysis helpers.

This module does not parse STL/3MF directly. Parsers provide normalized
triangle metadata; these functions evaluate placement candidates deterministically.
"""

from __future__ import annotations

import math

from .mesh import FlatPlacement, MeshMetadata
from .studio import Vector3


def _length(vector: Vector3) -> float:
    return math.sqrt(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z)


def _normalized(vector: Vector3) -> Vector3:
    length = _length(vector)
    if length == 0:
        raise ValueError("face normal must not be zero")
    return Vector3(vector.x / length, vector.y / length, vector.z / length)


def _rotation_to_downward(normal: Vector3) -> tuple[float, float, float]:
    n = _normalized(normal)
    yaw = math.degrees(math.atan2(n.y, n.x))
    pitch = math.degrees(math.acos(max(-1.0, min(1.0, -n.z))))
    return (0.0, pitch, yaw)


def choose_flat_placement(metadata: MeshMetadata) -> FlatPlacement:
    candidates = tuple(face for face in metadata.candidate_faces if face.area > 0)
    if not candidates:
        raise ValueError("mesh does not contain placement candidates")

    best = max(candidates, key=lambda face: face.area)
    total_area = sum(face.area for face in candidates)
    confidence = best.area / total_area if total_area > 0 else 0.0
    return FlatPlacement(
        rotation=_rotation_to_downward(best.normal),
        support_area=best.area,
        normal=best.normal,
        confidence=confidence,
    )
