"""Deterministic geometry-aware scene commands."""

from __future__ import annotations

from dataclasses import replace

from .common import new_id
from .scene_commands import SceneCommand, _replace_plate, _required_plate
from .studio import ProjectRecord, SceneObject, Transform3D


def _required_object(project: ProjectRecord, plate_id: str, object_id: str) -> tuple:
    plate = _required_plate(project, plate_id)
    for scene_object in plate.objects:
        if scene_object.id == object_id:
            return plate, scene_object
    raise KeyError(object_id)


class CenterObjectOnPlate(SceneCommand):
    def __init__(self, plate_id: str, object_id: str) -> None:
        self.plate_id = plate_id
        self.object_id = object_id

    def apply(self, project: ProjectRecord) -> ProjectRecord:
        plate, scene_object = _required_object(project, self.plate_id, self.object_id)
        if scene_object.locked:
            raise ValueError("locked objects cannot be centered")
        transform = replace(
            scene_object.transform,
            position=(plate.size[0] / 2.0, plate.size[1] / 2.0, scene_object.transform.position[2]),
        )
        objects = tuple(
            replace(item, transform=transform) if item.id == self.object_id else item
            for item in plate.objects
        )
        return _replace_plate(project, replace(plate, objects=objects))


class PlaceObjectOnBed(SceneCommand):
    def __init__(self, plate_id: str, object_id: str) -> None:
        self.plate_id = plate_id
        self.object_id = object_id

    def apply(self, project: ProjectRecord) -> ProjectRecord:
        plate, scene_object = _required_object(project, self.plate_id, self.object_id)
        if scene_object.locked:
            raise ValueError("locked objects cannot be moved")
        if scene_object.bounds is None:
            raise ValueError("object bounds are required to place an object on the bed")
        scale_z = scene_object.transform.scale[2]
        z = -scene_object.bounds.minimum.z * scale_z
        position = scene_object.transform.position
        transform = replace(scene_object.transform, position=(position[0], position[1], z))
        objects = tuple(
            replace(item, transform=transform) if item.id == self.object_id else item
            for item in plate.objects
        )
        return _replace_plate(project, replace(plate, objects=objects))


class DuplicateObjects(SceneCommand):
    def __init__(
        self,
        plate_id: str,
        object_ids: tuple[str, ...],
        offset: tuple[float, float, float] = (10.0, 10.0, 0.0),
    ) -> None:
        self.plate_id = plate_id
        self.object_ids = object_ids
        self.offset = offset

    def apply(self, project: ProjectRecord) -> ProjectRecord:
        plate = _required_plate(project, self.plate_id)
        selected = [item for item in plate.objects if item.id in self.object_ids]
        missing = set(self.object_ids) - {item.id for item in selected}
        if missing:
            raise KeyError(sorted(missing)[0])
        duplicates: list[SceneObject] = []
        for item in selected:
            position = item.transform.position
            duplicates.append(
                replace(
                    item,
                    id=new_id("object"),
                    name=f"{item.name} Copy",
                    transform=replace(
                        item.transform,
                        position=(
                            position[0] + self.offset[0],
                            position[1] + self.offset[1],
                            position[2] + self.offset[2],
                        ),
                    ),
                    locked=False,
                )
            )
        return _replace_plate(
            project,
            replace(plate, objects=plate.objects + tuple(duplicates)),
        )