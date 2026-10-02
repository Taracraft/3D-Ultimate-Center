"""Mesh analysis application service."""

from __future__ import annotations

from dataclasses import replace

from .mesh_analysis import choose_flat_placement
from .scene_commands import _replace_plate, _required_plate
from .sqlite_mesh import SqliteMeshRepository
from .studio import ProjectRecord


class MeshService:
    def __init__(self, repository: SqliteMeshRepository) -> None:
        self._repository = repository

    def place_object_flat(
        self,
        project: ProjectRecord,
        plate_id: str,
        object_id: str,
    ) -> ProjectRecord:
        plate = _required_plate(project, plate_id)
        target = next((item for item in plate.objects if item.id == object_id), None)
        if target is None:
            raise KeyError(object_id)
        if target.locked:
            raise ValueError("locked objects cannot be rotated")

        metadata = self._repository.get(target.asset_id)
        if metadata is None:
            raise ValueError("mesh metadata is not available for this object")
        placement = choose_flat_placement(metadata)
        transform = replace(target.transform, rotation=placement.rotation)
        objects = tuple(
            replace(item, transform=transform) if item.id == object_id else item
            for item in plate.objects
        )
        return _replace_plate(project, replace(plate, objects=objects))