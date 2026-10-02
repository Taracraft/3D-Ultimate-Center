"""SQLite repositories for mesh metadata and preview jobs."""

from __future__ import annotations

import json
import sqlite3

from .mesh import MeshFace, MeshMetadata
from .preview_jobs import PreviewJobRecord, PreviewJobStatus
from .studio import Bounds3D, Vector3


class SqliteMeshRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, asset_id: str) -> MeshMetadata | None:
        row = self._connection.execute(
            "SELECT * FROM mesh_metadata WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
        if row is None:
            return None
        faces_data = json.loads(row["candidate_faces_json"])
        faces = tuple(
            MeshFace(
                normal=Vector3(**item["normal"]),
                area=float(item["area"]),
                centroid=Vector3(**item["centroid"]),
            )
            for item in faces_data
        )
        return MeshMetadata(
            triangle_count=row["triangle_count"],
            vertex_count=row["vertex_count"],
            bounds=Bounds3D(
                minimum=Vector3(row["min_x"], row["min_y"], row["min_z"]),
                maximum=Vector3(row["max_x"], row["max_y"], row["max_z"]),
            ),
            volume_mm3=row["volume_mm3"],
            manifold=None if row["manifold"] is None else bool(row["manifold"]),
            watertight=None if row["watertight"] is None else bool(row["watertight"]),
            candidate_faces=faces,
        )

    def save(self, asset_id: str, metadata: MeshMetadata, analyzed_at: str) -> None:
        faces = [
            {
                "normal": {
                    "x": face.normal.x,
                    "y": face.normal.y,
                    "z": face.normal.z,
                },
                "area": face.area,
                "centroid": {
                    "x": face.centroid.x,
                    "y": face.centroid.y,
                    "z": face.centroid.z,
                },
            }
            for face in metadata.candidate_faces
        ]
        bounds = metadata.bounds
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO mesh_metadata (
                    asset_id, triangle_count, vertex_count,
                    min_x, min_y, min_z, max_x, max_y, max_z,
                    volume_mm3, manifold, watertight,
                    candidate_faces_json, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    triangle_count = excluded.triangle_count,
                    vertex_count = excluded.vertex_count,
                    min_x = excluded.min_x,
                    min_y = excluded.min_y,
                    min_z = excluded.min_z,
                    max_x = excluded.max_x,
                    max_y = excluded.max_y,
                    max_z = excluded.max_z,
                    volume_mm3 = excluded.volume_mm3,
                    manifold = excluded.manifold,
                    watertight = excluded.watertight,
                    candidate_faces_json = excluded.candidate_faces_json,
                    analyzed_at = excluded.analyzed_at
                """,
                (
                    asset_id,
                    metadata.triangle_count,
                    metadata.vertex_count,
                    bounds.minimum.x,
                    bounds.minimum.y,
                    bounds.minimum.z,
                    bounds.maximum.x,
                    bounds.maximum.y,
                    bounds.maximum.z,
                    metadata.volume_mm3,
                    None if metadata.manifold is None else int(metadata.manifold),
                    None if metadata.watertight is None else int(metadata.watertight),
                    json.dumps(faces, separators=(",", ":")),
                    analyzed_at,
                ),
            )


class SqlitePreviewJobRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, job_id: str) -> PreviewJobRecord | None:
        row = self._connection.execute(
            "SELECT * FROM preview_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return PreviewJobRecord(
            id=row["id"],
            asset_id=row["asset_id"],
            status=PreviewJobStatus(row["status"]),
            progress=row["progress"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            preview_asset_id=row["preview_asset_id"],
            error_code=row["error_code"],
            error_message=row["error_message"],
        )

    def save(self, job: PreviewJobRecord) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO preview_jobs (
                    id, asset_id, status, progress, preview_asset_id,
                    error_code, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    progress = excluded.progress,
                    preview_asset_id = excluded.preview_asset_id,
                    error_code = excluded.error_code,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at
                """,
                (
                    job.id,
                    job.asset_id,
                    job.status.value,
                    job.progress,
                    job.preview_asset_id,
                    job.error_code,
                    job.error_message,
                    job.created_at,
                    job.updated_at,
                ),
            )