"""SQLite-backed slicing repositories."""

from __future__ import annotations

import json
import sqlite3

from .profiles import ProfileSelection
from .slice_artifacts import GCodeLayer, GCodeMetadata, SliceArtifactKind, SliceArtifactRecord
from .slicing import SliceJobRecord, SliceJobStatus


class SqliteSliceJobRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, job_id: str) -> SliceJobRecord | None:
        row = self._connection.execute(
            "SELECT * FROM slice_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        selection_data = json.loads(row["profile_selection_json"])
        selection = ProfileSelection(
            printer_profile_id=selection_data.get("printer_profile_id"),
            nozzle_profile_id=selection_data.get("nozzle_profile_id"),
            process_profile_id=selection_data.get("process_profile_id"),
            build_plate_profile_id=selection_data.get("build_plate_profile_id"),
            filament_profile_ids=tuple(selection_data.get("filament_profile_ids", ())),
        )
        return SliceJobRecord(
            id=row["id"],
            project_id=row["project_id"],
            plate_id=row["plate_id"],
            provider_id=row["provider_id"],
            status=SliceJobStatus(row["status"]),
            progress=row["progress"],
            profile_selection=selection,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            artifact_asset_ids=tuple(json.loads(row["artifact_asset_ids_json"])),
            error_code=row["error_code"],
            error_message=row["error_message"],
        )

    def save(self, job: SliceJobRecord) -> None:
        selection = {
            "printer_profile_id": job.profile_selection.printer_profile_id,
            "nozzle_profile_id": job.profile_selection.nozzle_profile_id,
            "process_profile_id": job.profile_selection.process_profile_id,
            "build_plate_profile_id": job.profile_selection.build_plate_profile_id,
            "filament_profile_ids": list(job.profile_selection.filament_profile_ids),
        }
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO slice_jobs (
                    id, project_id, plate_id, provider_id, status, progress,
                    profile_selection_json, artifact_asset_ids_json,
                    error_code, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    progress = excluded.progress,
                    profile_selection_json = excluded.profile_selection_json,
                    artifact_asset_ids_json = excluded.artifact_asset_ids_json,
                    error_code = excluded.error_code,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at
                """,
                (
                    job.id,
                    job.project_id,
                    job.plate_id,
                    job.provider_id,
                    job.status.value,
                    job.progress,
                    json.dumps(selection, separators=(",", ":")),
                    json.dumps(job.artifact_asset_ids, separators=(",", ":")),
                    job.error_code,
                    job.error_message,
                    job.created_at,
                    job.updated_at,
                ),
            )

    def list_by_status(self, status: SliceJobStatus, limit: int = 100) -> list[SliceJobRecord]:
        rows = self._connection.execute(
            "SELECT id FROM slice_jobs WHERE status = ? ORDER BY created_at LIMIT ?",
            (status.value, limit),
        ).fetchall()
        return [job for row in rows if (job := self.get(row["id"])) is not None]


class SqliteSliceArtifactRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add(self, artifact: SliceArtifactRecord) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO slice_artifacts (
                    id, slice_job_id, asset_id, kind, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    artifact.id,
                    artifact.slice_job_id,
                    artifact.asset_id,
                    artifact.kind.value,
                    artifact.created_at,
                ),
            )

    def list_for_job(self, job_id: str) -> list[SliceArtifactRecord]:
        rows = self._connection.execute(
            "SELECT * FROM slice_artifacts WHERE slice_job_id = ? ORDER BY created_at",
            (job_id,),
        ).fetchall()
        return [
            SliceArtifactRecord(
                id=row["id"],
                slice_job_id=row["slice_job_id"],
                asset_id=row["asset_id"],
                kind=SliceArtifactKind(row["kind"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]


class SqliteGCodeRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save(self, asset_id: str, metadata: GCodeMetadata, parsed_at: str) -> None:
        bounds = metadata.bounds or (None, None, None, None, None, None)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO gcode_metadata (
                    asset_id, layer_count, estimated_time_seconds,
                    filament_mm, filament_grams, filament_cost,
                    min_x, min_y, min_z, max_x, max_y, max_z, parsed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    layer_count = excluded.layer_count,
                    estimated_time_seconds = excluded.estimated_time_seconds,
                    filament_mm = excluded.filament_mm,
                    filament_grams = excluded.filament_grams,
                    filament_cost = excluded.filament_cost,
                    min_x = excluded.min_x,
                    min_y = excluded.min_y,
                    min_z = excluded.min_z,
                    max_x = excluded.max_x,
                    max_y = excluded.max_y,
                    max_z = excluded.max_z,
                    parsed_at = excluded.parsed_at
                """,
                (
                    asset_id,
                    metadata.layer_count,
                    metadata.estimated_time_seconds,
                    metadata.filament_mm,
                    metadata.filament_grams,
                    metadata.filament_cost,
                    *bounds,
                    parsed_at,
                ),
            )
            self._connection.execute(
                "DELETE FROM gcode_layers WHERE asset_id = ?",
                (asset_id,),
            )
            for layer in metadata.layers:
                self._connection.execute(
                    """
                    INSERT INTO gcode_layers (
                        asset_id, layer_index, z_height, time_seconds,
                        filament_mm, move_count, extrusion_count, travel_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        asset_id,
                        layer.layer_index,
                        layer.z_height,
                        layer.time_seconds,
                        layer.filament_mm,
                        layer.move_count,
                        layer.extrusion_count,
                        layer.travel_count,
                    ),
                )

    def get(self, asset_id: str) -> GCodeMetadata | None:
        row = self._connection.execute(
            "SELECT * FROM gcode_metadata WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
        if row is None:
            return None
        layer_rows = self._connection.execute(
            "SELECT * FROM gcode_layers WHERE asset_id = ? ORDER BY layer_index",
            (asset_id,),
        ).fetchall()
        layers = tuple(
            GCodeLayer(
                layer_index=item["layer_index"],
                z_height=item["z_height"],
                time_seconds=item["time_seconds"],
                filament_mm=item["filament_mm"],
                move_count=item["move_count"],
                extrusion_count=item["extrusion_count"],
                travel_count=item["travel_count"],
            )
            for item in layer_rows
        )
        raw_bounds = (
            row["min_x"], row["min_y"], row["min_z"],
            row["max_x"], row["max_y"], row["max_z"],
        )
        bounds = None if all(value is None for value in raw_bounds) else raw_bounds
        return GCodeMetadata(
            layer_count=row["layer_count"],
            estimated_time_seconds=row["estimated_time_seconds"],
            filament_mm=row["filament_mm"],
            filament_grams=row["filament_grams"],
            filament_cost=row["filament_cost"],
            bounds=bounds,
            layers=layers,
        )