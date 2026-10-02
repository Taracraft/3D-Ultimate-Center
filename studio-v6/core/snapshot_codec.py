"""Project snapshot encoding and decoding."""

from __future__ import annotations

import json
from dataclasses import asdict

from .studio import Bounds3D, PlateRecord, ProjectRecord, SceneObject, Transform3D, Vector3


def encode_project(project: ProjectRecord) -> str:
    return json.dumps(asdict(project), separators=(",", ":"), sort_keys=True)


def decode_project(payload: str) -> ProjectRecord:
    data = json.loads(payload)
    plates: list[PlateRecord] = []
    for plate_data in data["plates"]:
        objects: list[SceneObject] = []
        for object_data in plate_data.get("objects", []):
            transform_data = object_data.get("transform", {})
            bounds_data = object_data.get("bounds")
            bounds = None
            if bounds_data is not None:
                bounds = Bounds3D(
                    minimum=Vector3(**bounds_data["minimum"]),
                    maximum=Vector3(**bounds_data["maximum"]),
                )
            objects.append(
                SceneObject(
                    id=object_data["id"],
                    asset_id=object_data["asset_id"],
                    name=object_data["name"],
                    transform=Transform3D(
                        position=tuple(transform_data.get("position", (0.0, 0.0, 0.0))),
                        rotation=tuple(transform_data.get("rotation", (0.0, 0.0, 0.0))),
                        scale=tuple(transform_data.get("scale", (1.0, 1.0, 1.0))),
                    ),
                    visible=bool(object_data.get("visible", True)),
                    locked=bool(object_data.get("locked", False)),
                    color=object_data.get("color"),
                    bounds=bounds,
                )
            )
        plates.append(
            PlateRecord(
                id=plate_data["id"],
                name=plate_data["name"],
                order_index=int(plate_data["order_index"]),
                objects=tuple(objects),
                size=tuple(plate_data.get("size", (256.0, 256.0))),
            )
        )
    return ProjectRecord(
        id=data["id"],
        name=data["name"],
        revision=int(data["revision"]),
        plates=tuple(plates),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )
