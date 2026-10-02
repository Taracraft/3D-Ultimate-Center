"""Immutable scene commands for Project Core."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from .studio import PlateRecord, ProjectRecord, SceneObject, Transform3D


class SceneCommand(Protocol):
    def apply(self, project: ProjectRecord) -> ProjectRecord: ...


def _replace_plate(project: ProjectRecord, updated: PlateRecord) -> ProjectRecord:
    plates = tuple(
        updated if plate.id == updated.id else plate
        for plate in project.plates
    )
    return replace(project, plates=plates)


def _required_plate(project: ProjectRecord, plate_id: str) -> PlateRecord:
    for plate in project.plates:
        if plate.id == plate_id:
            return plate
    raise KeyError(plate_id)


class AddPlate:
    def __init__(self, plate: PlateRecord) -> None:
        self.plate = plate

    def apply(self, project: ProjectRecord) -> ProjectRecord:
        if any(plate.id == self.plate.id for plate in project.plates):
            raise ValueError(f"duplicate plate id: {self.plate.id}")
        return replace(project, plates=project.plates + (self.plate,))


class RemovePlate:
    def __init__(self, plate_id: str) -> None:
        self.plate_id = plate_id

    def apply(self, project: ProjectRecord) -> ProjectRecord:
        if len(project.plates) <= 1:
            raise ValueError("a project must contain at least one plate")
        plates = tuple(plate for plate in project.plates if plate.id != self.plate_id)
        if len(plates) == len(project.plates):
            raise KeyError(self.plate_id)
        return replace(project, plates=plates)


class AddObject:
    def __init__(self, plate_id: str, scene_object: SceneObject) -> None:
        self.plate_id = plate_id
        self.scene_object = scene_object

    def apply(self, project: ProjectRecord) -> ProjectRecord:
        plate = _required_plate(project, self.plate_id)
        if any(item.id == self.scene_object.id for item in plate.objects):
            raise ValueError(f"duplicate object id: {self.scene_object.id}")
        return _replace_plate(
            project,
            replace(plate, objects=plate.objects + (self.scene_object,)),
        )


class RemoveObject:
    def __init__(self, plate_id: str, object_id: str) -> None:
        self.plate_id = plate_id
        self.object_id = object_id

    def apply(self, project: ProjectRecord) -> ProjectRecord:
        plate = _required_plate(project, self.plate_id)
        objects = tuple(item for item in plate.objects if item.id != self.object_id)
        if len(objects) == len(plate.objects):
            raise KeyError(self.object_id)
        return _replace_plate(project, replace(plate, objects=objects))


class SetObjectTransform:
    def __init__(self, plate_id: str, object_id: str, transform: Transform3D) -> None:
        self.plate_id = plate_id
        self.object_id = object_id
        self.transform = transform

    def apply(self, project: ProjectRecord) -> ProjectRecord:
        plate = _required_plate(project, self.plate_id)
        found = False
        objects: list[SceneObject] = []
        for item in plate.objects:
            if item.id == self.object_id:
                if item.locked:
                    raise ValueError("locked objects cannot be transformed")
                item = replace(item, transform=self.transform)
                found = True
            objects.append(item)
        if not found:
            raise KeyError(self.object_id)
        return _replace_plate(project, replace(plate, objects=tuple(objects)))


class SetObjectColor:
    def __init__(self, plate_id: str, object_id: str, color: str | None) -> None:
        self.plate_id = plate_id
        self.object_id = object_id
        self.color = color

    def apply(self, project: ProjectRecord) -> ProjectRecord:
        plate = _required_plate(project, self.plate_id)
        found = False
        objects: list[SceneObject] = []
        for item in plate.objects:
            if item.id == self.object_id:
                item = replace(item, color=self.color)
                found = True
            objects.append(item)
        if not found:
            raise KeyError(self.object_id)
        return _replace_plate(project, replace(plate, objects=tuple(objects)))