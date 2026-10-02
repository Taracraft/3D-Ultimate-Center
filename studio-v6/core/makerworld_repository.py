"""SQLite persistence for MakerWorld metadata, imports and asset provenance."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from .makerworld import MakerWorldModel


class MakerWorldRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save_model(self, model: MakerWorldModel, fetched_at: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO makerworld_models (
                    model_id, title, model_url, creator_id, creator_name,
                    license_name, license_url, thumbnail_url,
                    metadata_json, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_id) DO UPDATE SET
                    title = excluded.title,
                    model_url = excluded.model_url,
                    creator_id = excluded.creator_id,
                    creator_name = excluded.creator_name,
                    license_name = excluded.license_name,
                    license_url = excluded.license_url,
                    thumbnail_url = excluded.thumbnail_url,
                    metadata_json = excluded.metadata_json,
                    fetched_at = excluded.fetched_at
                """,
                (
                    model.id,
                    model.title,
                    model.model_url,
                    model.creator.id,
                    model.creator.name,
                    model.license_name,
                    model.license_url,
                    model.thumbnail_url,
                    json.dumps(asdict(model), separators=(",", ":")),
                    fetched_at,
                ),
            )

    def save_import(
        self,
        *,
        import_id: str,
        model_id: str,
        profile_id: str | None,
        destination: str,
        source_url: str,
        created_at: str,
        license_acknowledged: bool,
        selected_profile: dict | None = None,
        asset_id: str | None = None,
        project_id: str | None = None,
        slice_job_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        selected_profile_json = (
            json.dumps(selected_profile, separators=(",", ":"))
            if selected_profile is not None
            else None
        )
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO makerworld_imports (
                    id, model_id, profile_id, destination,
                    asset_id, project_id, slice_job_id,
                    source_url, license_acknowledged, selected_profile_json,
                    created_at, error_code, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    model_id,
                    profile_id,
                    destination,
                    asset_id,
                    project_id,
                    slice_job_id,
                    source_url,
                    1 if license_acknowledged else 0,
                    selected_profile_json,
                    created_at,
                    error_code,
                    error_message,
                ),
            )
            if asset_id is not None and error_code is None:
                self._connection.execute(
                    """
                    INSERT INTO makerworld_asset_links (
                        asset_id, model_id, import_id,
                        selected_profile_id, selected_profile_json, linked_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(asset_id) DO UPDATE SET
                        model_id = excluded.model_id,
                        import_id = excluded.import_id,
                        selected_profile_id = excluded.selected_profile_id,
                        selected_profile_json = excluded.selected_profile_json,
                        linked_at = excluded.linked_at
                    """,
                    (
                        asset_id,
                        model_id,
                        import_id,
                        profile_id,
                        selected_profile_json,
                        created_at,
                    ),
                )

    def get_asset_info(self, asset_id: str) -> dict | None:
        row = self._connection.execute(
            """
            SELECT
                links.asset_id,
                links.model_id,
                links.selected_profile_id,
                links.selected_profile_json,
                links.linked_at,
                models.metadata_json
            FROM makerworld_asset_links AS links
            JOIN makerworld_models AS models
              ON models.model_id = links.model_id
            WHERE links.asset_id = ?
            """,
            (asset_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "asset_id": row["asset_id"],
            "model": json.loads(row["metadata_json"]),
            "selected_profile_id": row["selected_profile_id"],
            "selected_profile": (
                json.loads(row["selected_profile_json"])
                if row["selected_profile_json"]
                else None
            ),
            "linked_at": row["linked_at"],
        }

    def has_asset_link(self, asset_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM makerworld_asset_links WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
        return row is not None
