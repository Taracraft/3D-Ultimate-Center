"""Persistent print planning queue for the 3D-Printer Control Center dashboard."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
import secrets
import threading
import time
from typing import Any

_LOCK = threading.Lock()
_MAX_QUANTITY = 30


def _safe_text(value: Any, *, limit: int = 512) -> str:
    return str(value or "").strip()[:limit]


def _safe_path(value: Any) -> str:
    raw = _safe_text(value, limit=1024).replace("\\", "/")
    if not raw:
        raise ValueError("Unsafe queue path")
    leading_slash = raw.startswith("/")
    path = PurePosixPath(raw.lstrip("/"))
    if not path.parts or ".." in path.parts:
        raise ValueError("Unsafe queue path")
    normalized = path.as_posix()
    return f"/{normalized}" if leading_slash else normalized


def _quantity(value: Any) -> int:
    try:
        quantity = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Quantity must be a number") from exc
    if quantity < 1 or quantity > _MAX_QUANTITY:
        raise ValueError(f"Quantity must be between 1 and {_MAX_QUANTITY}")
    return quantity


def _scheduled_for(value: Any) -> str:
    return _safe_text(value, limit=64)


def _preview_data_url(value: Any) -> str:
    preview = _safe_text(value, limit=900_000)
    if preview and not preview.startswith("data:image/"):
        return ""
    return preview


class PrintQueueRepository:
    """Store planned print jobs in a small atomic JSON file."""

    def __init__(self, queue_file: Path) -> None:
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.queue_file.exists():
            return []
        try:
            payload = json.loads(self.queue_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.queue_file.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.queue_file)

    def list(self, serial: str) -> dict[str, Any]:
        normalized_serial = _safe_text(serial, limit=128)
        with _LOCK:
            items = [
                deepcopy(item)
                for item in self._read()
                if item.get("serial") == normalized_serial
            ]
        items.sort(key=lambda item: int(item.get("position", 0)))
        return {"items": items}

    def add(
        self,
        *,
        serial: str,
        source: str,
        path: str,
        name: str = "",
        quantity: int = 1,
        scheduled_for: str = "",
        preview_data_url: str = "",
    ) -> dict[str, Any]:
        normalized_serial = _safe_text(serial, limit=128)
        if not normalized_serial:
            raise ValueError("Printer serial is required")
        if source not in {"archive", "sd"}:
            raise ValueError("Unknown queue source")
        normalized_path = _safe_path(path)
        normalized_name = _safe_text(name, limit=255) or normalized_path.rsplit("/", 1)[-1]
        if not normalized_name.lower().endswith(".3mf"):
            raise ValueError("Only .3mf models can be planned")

        with _LOCK:
            items = self._read()
            serial_items = [item for item in items if item.get("serial") == normalized_serial]
            entry = {
                "id": secrets.token_urlsafe(12),
                "serial": normalized_serial,
                "source": source,
                "path": normalized_path,
                "name": normalized_name,
                "quantity": _quantity(quantity),
                "scheduled_for": _scheduled_for(scheduled_for),
                "preview_data_url": _preview_data_url(preview_data_url),
                "status": "planned",
                "created_at": time.time(),
                "position": len(serial_items),
            }
            items.append(entry)
            self._write(items)
        return deepcopy(entry)

    def update(
        self,
        *,
        serial: str,
        queue_id: str,
        quantity: int | None = None,
        scheduled_for: str | None = None,
    ) -> dict[str, Any]:
        normalized_serial = _safe_text(serial, limit=128)
        normalized_id = _safe_text(queue_id, limit=128)
        with _LOCK:
            items = self._read()
            entry = next(
                (
                    item
                    for item in items
                    if item.get("serial") == normalized_serial
                    and item.get("id") == normalized_id
                ),
                None,
            )
            if entry is None:
                raise ValueError("Queue item not found")
            if quantity is not None:
                entry["quantity"] = _quantity(quantity)
            if scheduled_for is not None:
                entry["scheduled_for"] = _scheduled_for(scheduled_for)
            self._write(items)
        return deepcopy(entry)

    def delete(self, *, serial: str, queue_id: str) -> None:
        normalized_serial = _safe_text(serial, limit=128)
        normalized_id = _safe_text(queue_id, limit=128)
        with _LOCK:
            items = self._read()
            remaining = [
                item
                for item in items
                if not (
                    item.get("serial") == normalized_serial
                    and item.get("id") == normalized_id
                )
            ]
            if len(remaining) == len(items):
                raise ValueError("Queue item not found")
            self._normalize_positions(remaining, normalized_serial)
            self._write(remaining)

    def move(self, *, serial: str, queue_id: str, direction: str) -> dict[str, Any]:
        normalized_serial = _safe_text(serial, limit=128)
        normalized_id = _safe_text(queue_id, limit=128)
        if direction not in {"up", "down"}:
            raise ValueError("Unknown move direction")
        with _LOCK:
            items = self._read()
            serial_items = sorted(
                [item for item in items if item.get("serial") == normalized_serial],
                key=lambda item: int(item.get("position", 0)),
            )
            index = next(
                (index for index, item in enumerate(serial_items) if item.get("id") == normalized_id),
                None,
            )
            if index is None:
                raise ValueError("Queue item not found")
            target = index - 1 if direction == "up" else index + 1
            if 0 <= target < len(serial_items):
                serial_items[index], serial_items[target] = serial_items[target], serial_items[index]
            for position, item in enumerate(serial_items):
                item["position"] = position
            self._write(items)
            result = serial_items[target if 0 <= target < len(serial_items) else index]
        return deepcopy(result)

    @staticmethod
    def _normalize_positions(items: list[dict[str, Any]], serial: str) -> None:
        serial_items = sorted(
            [item for item in items if item.get("serial") == serial],
            key=lambda item: int(item.get("position", 0)),
        )
        for position, item in enumerate(serial_items):
            item["position"] = position