"""SQLite-backed Asset Core repository."""

from __future__ import annotations

import sqlite3

from .assets import AssetFormat, AssetKind, AssetRecord


class SqliteAssetRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, asset_id: str) -> AssetRecord | None:
        row = self._connection.execute(
            "SELECT * FROM assets WHERE id = ?",
            (asset_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def find_by_digest(self, digest: str) -> AssetRecord | None:
        row = self._connection.execute(
            "SELECT * FROM assets WHERE digest = ?",
            (digest.lower(),),
        ).fetchone()
        return self._from_row(row) if row else None

    def add(self, asset: AssetRecord) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO assets (
                    id, kind, format, digest, size_bytes,
                    original_name, storage_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset.id,
                    asset.kind.value,
                    asset.format.value,
                    asset.digest.lower(),
                    asset.size_bytes,
                    asset.original_name,
                    asset.storage_key,
                    asset.created_at,
                ),
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> AssetRecord:
        return AssetRecord(
            id=row["id"],
            kind=AssetKind(row["kind"]),
            format=AssetFormat(row["format"]),
            digest=row["digest"],
            size_bytes=row["size_bytes"],
            original_name=row["original_name"],
            storage_key=row["storage_key"],
            created_at=row["created_at"],
        )
