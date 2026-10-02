"""SQLite-backed Project Core repository."""

from __future__ import annotations

import json
import sqlite3

from .studio import Bounds3D, PlateRecord, ProjectRecord, SceneObject, Transform3D, Vector3


class SqliteProjectRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, project_id: str) -> ProjectRecord | None:
        project_row = self._connection.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if project_row is None:
            return None
        plate_rows = self._connection.execute(
            "SELECT * FROM plates WHERE project_id = ? ORDER BY order_index",
            (project_id,),
        ).fetchall()
        return ProjectRecord(
            id=project_row["id"],
            name=project_row["name"],
            revision=project_row["revision"],
            plates=tuple(self._plate_from_row(row) for row in plate_rows),
            created_at=project_row["created_at"],
            updated_at=project_row["updated_at"],
        )

    def save(self, project: ProjectRecord) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO projects (id, name, revision, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    revision = excluded.revision,
                    updated_at = excluded.updated_at
                """,
                (
                    project.id,
                    project.name,
                    project.revision,
                    project.created_at,
                    project.updated_at,
                ),
            )

            current_plate_ids = tuple(plate.id for plate in project.plates)
            self._delete_stale_plates(project.id, current_plate_ids)

            for plate in project.plates:
                self._save_plate(project.id, plate)

    def save_revision(self, project: ProjectRecord, snapshot_json: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO project_revisions (
                    project_id, revision, snapshot_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (project.id, project.revision, snapshot_json, project.updated_at),
            )

    def snapshot(self, project_id: str, revision: int | None = None) -> str | None:
        if revision is None:
            row = self._connection.execute(
                """
                SELECT snapshot_json FROM project_revisions
                WHERE project_id = ? ORDER BY revision DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        else:
            row = self._connection.execute(
                """
                SELECT snapshot_json FROM project_revisions
                WHERE project_id = ? AND revision = ?
                """,
                (project_id, revision),
            ).fetchone()
        return row[0] if row else None

    def latest_snapshot(self, project_id: str) -> str | None:
        return self.snapshot(project_id)

    def _delete_stale_plates(
        self,
        project_id: str,
        current_plate_ids: tuple[str, ...],
    ) -> None:
        existing_rows = self._connection.execute(
            "SELECT id FROM plates WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        existing_ids = {row["id"] for row in existing_rows}
        stale_ids = existing_ids.difference(current_plate_ids)

        for plate_id in stale_ids:
            self._delete_plate(plate_id)

    def _delete_plate(self, plate_id: str) -> None:
        object_rows = self._connection.execute(
            "SELECT id FROM scene_objects WHERE plate_id = ?",
            (plate_id,),
        ).fetchall()
        object_ids = tuple(row["id"] for row in object_rows)

        for object_id in object_ids:
            self._connection.execute(
                "DELETE FROM object_geometry WHERE object_id = ?",
                (object_id,),
            )

        self._connection.execute(
            "DELETE FROM scene_objects WHERE plate_id = ?",
            (plate_id,),
        )
        self._connection.execute(
            "DELETE FROM plate_geometry WHERE plate_id = ?",
            (plate_id,),
        )
        self._connection.execute(
            "DELETE FROM plates WHERE id = ?",
            (plate_id,),
        )

    def _save_plate(self, project_id: str, plate: PlateRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO plates (id, project_id, name, order_index)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                project_id = excluded.project_id,
                name = excluded.name,
                order_index = excluded.order_index
            """,
            (plate.id, project_id, plate.name, plate.order_index),
        )
        self._connection.execute(
            """
            INSERT INTO plate_geometry (plate_id, width, depth)
            VALUES (?, ?, ?)
            ON CONFLICT(plate_id) DO UPDATE SET
                width = excluded.width,
                depth = excluded.depth
            """,
            (plate.id, plate.size[0], plate.size[1]),
        )

        current_object_ids = tuple(item.id for item in plate.objects)
        self._delete_stale_objects(plate.id, current_object_ids)

        for scene_object in plate.objects:
            self._save_object(plate.id, scene_object)

    def _delete_stale_objects(
        self,
        plate_id: str,
        current_object_ids: tuple[str, ...],
    ) -> None:
        existing_rows = self._connection.execute(
            "SELECT id FROM scene_objects WHERE plate_id = ?",
            (plate_id,),
        ).fetchall()
        existing_ids = {row["id"] for row in existing_rows}
        stale_ids = existing_ids.difference(current_object_ids)

        for object_id in stale_ids:
            self._connection.execute(
                "DELETE FROM object_geometry WHERE object_id = ?",
                (object_id,),
            )
            self._connection.execute(
                "DELETE FROM scene_objects WHERE id = ?",
                (object_id,),
            )

    def _save_object(self, plate_id: str, scene_object: SceneObject) -> None:
        transform = {
            "position": scene_object.transform.position,
            "rotation": scene_object.transform.rotation,
            "scale": scene_object.transform.scale,
        }
        self._connection.execute(
            """
            INSERT INTO scene_objects (
                id, plate_id, asset_id, name, transform_json,
                visible, locked, color
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                plate_id = excluded.plate_id,
                asset_id = excluded.asset_id,
                name = excluded.name,
                transform_json = excluded.transform_json,
                visible = excluded.visible,
                locked = excluded.locked,
                color = excluded.color
            """,
            (
                scene_object.id,
                plate_id,
                scene_object.asset_id,
                scene_object.name,
                json.dumps(transform, separators=(",", ":")),
                1 if scene_object.visible else 0,
                1 if scene_object.locked else 0,
                scene_object.color,
            ),
        )

        if scene_object.bounds is None:
            self._connection.execute(
                "DELETE FROM object_geometry WHERE object_id = ?",
                (scene_object.id,),
            )
            return

        bounds = scene_object.bounds
        self._connection.execute(
            """
            INSERT INTO object_geometry (
                object_id, min_x, min_y, min_z, max_x, max_y, max_z
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(object_id) DO UPDATE SET
                min_x = excluded.min_x,
                min_y = excluded.min_y,
                min_z = excluded.min_z,
                max_x = excluded.max_x,
                max_y = excluded.max_y,
                max_z = excluded.max_z
            """,
            (
                scene_object.id,
                bounds.minimum.x,
                bounds.minimum.y,
                bounds.minimum.z,
                bounds.maximum.x,
                bounds.maximum.y,
                bounds.maximum.z,
            ),
        )

    def _plate_from_row(self, row: sqlite3.Row) -> PlateRecord:
        object_rows = self._connection.execute(
            "SELECT * FROM scene_objects WHERE plate_id = ? ORDER BY rowid",
            (row["id"],),
        ).fetchall()
        geometry = self._connection.execute(
            "SELECT width, depth FROM plate_geometry WHERE plate_id = ?",
            (row["id"],),
        ).fetchone()
        size = (
            (float(geometry["width"]), float(geometry["depth"]))
            if geometry
            else (256.0, 256.0)
        )
        return PlateRecord(
            id=row["id"],
            name=row["name"],
            order_index=row["order_index"],
            objects=tuple(self._object_from_row(item) for item in object_rows),
            size=size,
        )

    def _object_from_row(self, row: sqlite3.Row) -> SceneObject:
        transform_data = json.loads(row["transform_json"])
        geometry = self._connection.execute(
            "SELECT * FROM object_geometry WHERE object_id = ?",
            (row["id"],),
        ).fetchone()
        bounds = None
        if geometry:
            bounds = Bounds3D(
                minimum=Vector3(
                    geometry["min_x"],
                    geometry["min_y"],
                    geometry["min_z"],
                ),
                maximum=Vector3(
                    geometry["max_x"],
                    geometry["max_y"],
                    geometry["max_z"],
                ),
            )
        return SceneObject(
            id=row["id"],
            asset_id=row["asset_id"],
            name=row["name"],
            transform=Transform3D(
                position=tuple(transform_data["position"]),
                rotation=tuple(transform_data["rotation"]),
                scale=tuple(transform_data["scale"]),
            ),
            visible=bool(row["visible"]),
            locked=bool(row["locked"]),
            color=row["color"],
            bounds=bounds,
        )