"""Create validated scene commands from API payloads."""

from __future__ import annotations

from .geometry_commands import CenterObjectOnPlate, DuplicateObjects, PlaceObjectOnBed
from .scene_commands import RemoveObject, SetObjectColor, SetObjectTransform
from .studio import Transform3D


def scene_command_from_payload(payload: dict):
    command = str(payload.get("command", "")).strip()
    plate_id = str(payload.get("plate_id", "")).strip()
    if not plate_id:
        raise ValueError("plate_id is required")

    if command == "remove_object":
        return RemoveObject(plate_id, _required(payload, "object_id"))
    if command == "set_color":
        return SetObjectColor(
            plate_id,
            _required(payload, "object_id"),
            payload.get("color"),
        )
    if command == "set_transform":
        transform = payload.get("transform") or {}
        return SetObjectTransform(
            plate_id,
            _required(payload, "object_id"),
            Transform3D(
                position=_vector(transform.get("position"), (0.0, 0.0, 0.0)),
                rotation=_vector(transform.get("rotation"), (0.0, 0.0, 0.0)),
                scale=_vector(transform.get("scale"), (1.0, 1.0, 1.0)),
            ),
        )
    if command == "center_object":
        return CenterObjectOnPlate(plate_id, _required(payload, "object_id"))
    if command == "place_on_bed":
        return PlaceObjectOnBed(plate_id, _required(payload, "object_id"))
    if command == "duplicate_objects":
        object_ids = tuple(str(value) for value in payload.get("object_ids", ()))
        if not object_ids:
            raise ValueError("object_ids must not be empty")
        offset = _vector(payload.get("offset"), (10.0, 10.0, 0.0))
        return DuplicateObjects(plate_id, object_ids, offset)
    raise ValueError(f"unsupported scene command: {command}")


def _required(payload: dict, key: str) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _vector(value, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if value is None:
        return default
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("vector values must contain exactly three numbers")
    return (float(value[0]), float(value[1]), float(value[2]))