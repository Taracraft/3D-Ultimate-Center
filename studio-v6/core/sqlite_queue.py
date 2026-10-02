"""SQLite-backed Queue Core repository."""

from __future__ import annotations

import sqlite3

from .queue import QueueItemRecord, QueueItemStatus


class SqliteQueueRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, item_id: str) -> QueueItemRecord | None:
        row = self._connection.execute(
            "SELECT * FROM queue_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            return None
        return QueueItemRecord(
            id=row["id"],
            printer_serial=row["printer_serial"],
            status=QueueItemStatus(row["status"]),
            quantity=row["quantity"],
            priority=row["priority"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            source_ref=row["source_ref"],
            source_kind=row["source_kind"],
            scheduled_for=row["scheduled_for"],
        )

    def save(self, item: QueueItemRecord) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO queue_items (
                    id, printer_serial, status, quantity, priority,
                    source_kind, source_ref, scheduled_for,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    printer_serial = excluded.printer_serial,
                    status = excluded.status,
                    quantity = excluded.quantity,
                    priority = excluded.priority,
                    source_kind = excluded.source_kind,
                    source_ref = excluded.source_ref,
                    scheduled_for = excluded.scheduled_for,
                    updated_at = excluded.updated_at
                """,
                (
                    item.id,
                    item.printer_serial,
                    item.status.value,
                    item.quantity,
                    item.priority,
                    item.source_kind,
                    item.source_ref,
                    item.scheduled_for,
                    item.created_at,
                    item.updated_at,
                ),
            )