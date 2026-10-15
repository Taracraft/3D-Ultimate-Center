"""SQLite-backed upload session repository."""

from __future__ import annotations

import sqlite3

from .uploads import UploadSession, UploadStatus


class SqliteUploadRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, upload_id: str) -> UploadSession | None:
        row = self._connection.execute(
            "SELECT * FROM upload_sessions WHERE id = ?",
            (upload_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def save(self, upload: UploadSession) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO upload_sessions (
                    id, original_name, expected_size, received_size, chunk_size,
                    source_ui, target, status, expected_digest, asset_id,
                    error_code, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    received_size = excluded.received_size,
                    status = excluded.status,
                    expected_digest = excluded.expected_digest,
                    asset_id = excluded.asset_id,
                    error_code = excluded.error_code,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at
                """,
                (
                    upload.id,
                    upload.original_name,
                    upload.expected_size,
                    upload.received_size,
                    upload.chunk_size,
                    upload.source_ui,
                    upload.target,
                    upload.status.value,
                    upload.expected_digest,
                    upload.asset_id,
                    upload.error_code,
                    upload.error_message,
                    upload.created_at,
                    upload.updated_at,
                ),
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> UploadSession:
        return UploadSession(
            id=row["id"],
            original_name=row["original_name"],
            expected_size=row["expected_size"],
            received_size=row["received_size"],
            chunk_size=row["chunk_size"],
            source_ui=row["source_ui"],
            target=row["target"],
            status=UploadStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expected_digest=row["expected_digest"],
            asset_id=row["asset_id"],
            error_code=row["error_code"],
            error_message=row["error_message"],
        )
