"""Gallery and queue handoff into Project Core."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from .common import new_id, utc_now
from .project_service import ProjectService, ProjectSession
from .scene_commands import AddObject
from .sqlite_assets import SqliteAssetRepository
from .sqlite_queue import SqliteQueueRepository
from .studio import SceneObject


@dataclass(slots=True, frozen=True)
class HandoffRecord:
    id: str
    source_kind: str
    source_ref: str
    target_project_id: str
    created_at: str
    metadata: dict[str, str]


class HandoffService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        assets: SqliteAssetRepository,
        queue: SqliteQueueRepository,
        projects: ProjectService,
    ) -> None:
        self._connection = connection
        self._assets = assets
        self._queue = queue
        self._projects = projects

    def gallery_asset_to_project(
        self,
        asset_id: str,
        project_id: str | None = None,
        plate_id: str | None = None,
    ) -> tuple[ProjectSession, HandoffRecord]:
        asset = self._assets.get(asset_id)
        if asset is None:
            raise KeyError(asset_id)
        session = self._target_session(project_id, asset.original_name)
        target_plate = plate_id or session.project.plates[0].id
        scene_object = SceneObject(
            id=new_id("object"),
            asset_id=asset.id,
            name=asset.original_name,
        )
        session.execute(AddObject(target_plate, scene_object))
        session.save()
        record = self._record(
            source_kind="gallery_asset",
            source_ref=asset.id,
            target_project_id=session.project.id,
            metadata={"plate_id": target_plate, "object_id": scene_object.id},
        )
        return session, record

    def queue_item_to_project(
        self,
        queue_item_id: str,
        project_id: str | None = None,
    ) -> tuple[ProjectSession, HandoffRecord]:
        item = self._queue.get(queue_item_id)
        if item is None:
            raise KeyError(queue_item_id)
        if item.source_kind != "asset":
            raise ValueError("only asset-backed queue items can be opened in Studio")
        session, _ = self.gallery_asset_to_project(item.source_ref, project_id)
        record = self._record(
            source_kind="queue_item",
            source_ref=item.id,
            target_project_id=session.project.id,
            metadata={"asset_id": item.source_ref},
        )
        return session, record

    def _target_session(self, project_id: str | None, name: str) -> ProjectSession:
        if project_id:
            return self._projects.open(project_id)
        project_name = name.rsplit(".", 1)[0] or "Untitled Project"
        return self._projects.create(project_name)

    def _record(
        self,
        *,
        source_kind: str,
        source_ref: str,
        target_project_id: str,
        metadata: dict[str, str],
    ) -> HandoffRecord:
        record = HandoffRecord(
            id=new_id("handoff"),
            source_kind=source_kind,
            source_ref=source_ref,
            target_project_id=target_project_id,
            created_at=utc_now(),
            metadata=metadata,
        )
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO project_handoffs (
                    id, source_kind, source_ref, target_project_id,
                    created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.source_kind,
                    record.source_ref,
                    record.target_project_id,
                    record.created_at,
                    json.dumps(record.metadata, separators=(",", ":")),
                ),
            )
        return record