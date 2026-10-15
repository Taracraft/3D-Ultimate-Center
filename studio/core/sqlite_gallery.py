"""SQLite-backed Gallery Core repository."""

from __future__ import annotations

import sqlite3

from .gallery import GalleryFolder, GalleryItem


class SqliteGalleryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add_folder(self, folder: GalleryFolder) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO gallery_folders (
                    id, parent_id, name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    folder.id,
                    folder.parent_id,
                    folder.name,
                    folder.created_at,
                    folder.updated_at,
                ),
            )

    def add_item(self, item: GalleryItem) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO gallery_items (
                    asset_id, folder_id, title, description,
                    favorite, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    folder_id = excluded.folder_id,
                    title = excluded.title,
                    description = excluded.description,
                    favorite = excluded.favorite,
                    updated_at = excluded.updated_at
                """,
                (
                    item.asset_id,
                    item.folder_id,
                    item.title,
                    item.description,
                    1 if item.favorite else 0,
                    item.created_at,
                    item.updated_at,
                ),
            )
            self._replace_tags(item.asset_id, item.tags)

    def get_item(self, asset_id: str) -> GalleryItem | None:
        row = self._connection.execute(
            "SELECT * FROM gallery_items WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def search(self, query: str = "", limit: int = 100) -> list[GalleryItem]:
        pattern = f"%{query.strip()}%"
        rows = self._connection.execute(
            """
            SELECT * FROM gallery_items
            WHERE title LIKE ? OR description LIKE ?
            ORDER BY favorite DESC, updated_at DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def _from_row(self, row: sqlite3.Row) -> GalleryItem:
        return GalleryItem(
            asset_id=row["asset_id"],
            folder_id=row["folder_id"],
            title=row["title"],
            description=row["description"],
            favorite=bool(row["favorite"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            tags=self._tags_for(row["asset_id"]),
        )

    def _replace_tags(self, asset_id: str, tags: tuple[str, ...]) -> None:
        self._connection.execute(
            "DELETE FROM gallery_item_tags WHERE asset_id = ?",
            (asset_id,),
        )
        for tag in sorted({value.strip() for value in tags if value.strip()}):
            tag_id = f"tag:{tag.casefold()}"
            self._connection.execute(
                "INSERT OR IGNORE INTO gallery_tags (id, name) VALUES (?, ?)",
                (tag_id, tag),
            )
            self._connection.execute(
                "INSERT INTO gallery_item_tags (asset_id, tag_id) VALUES (?, ?)",
                (asset_id, tag_id),
            )

    def _tags_for(self, asset_id: str) -> tuple[str, ...]:
        rows = self._connection.execute(
            """
            SELECT gallery_tags.name
            FROM gallery_tags
            JOIN gallery_item_tags ON gallery_item_tags.tag_id = gallery_tags.id
            WHERE gallery_item_tags.asset_id = ?
            ORDER BY gallery_tags.name
            """,
            (asset_id,),
        ).fetchall()
        return tuple(row[0] for row in rows)
