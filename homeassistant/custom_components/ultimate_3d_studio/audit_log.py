"""Persistent, bounded and sanitized audit log for Ultimate 3D Studio."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Iterable
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .audit_safety import sanitize_audit_value
from .const import DOMAIN

STORE_VERSION = 1
STORE_KEY = "ultimate_3d_studio.audit_log"
DATA_AUDIT_LOG = "audit_log"
MAX_EVENTS = 10_000
MAX_RETURNED_EVENTS = 5_000


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalized_categories(value: str | Iterable[str] | None) -> set[str]:
    if value is None:
        return set()
    values = [value] if isinstance(value, str) else list(value)
    return {str(item).strip().casefold() for item in values if str(item).strip()}


class StudioAuditLog:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._events: list[dict[str, Any]] = []
        self._loaded = False

    async def async_load(self) -> None:
        if self._loaded:
            return
        stored = await self._store.async_load() or {}
        events = stored.get("events", [])
        self._events = [item for item in events if isinstance(item, dict)][-MAX_EVENTS:]
        self._loaded = True

    async def async_append(
        self,
        *,
        category: str,
        component: str,
        event: str,
        status: str,
        source: str = "backend",
        actor: str | None = None,
        correlation_id: str | None = None,
        job_id: str | None = None,
        printer_id: str | None = None,
        duration_ms: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.async_load()
        record = {
            "id": uuid4().hex,
            "timestamp": _now(),
            "correlation_id": correlation_id or uuid4().hex,
            "job_id": job_id,
            "printer_id": printer_id,
            "category": str(category or "System"),
            "component": str(component or "unknown"),
            "event": str(event or "event"),
            "status": str(status or "info"),
            "source": str(source or "backend"),
            "actor": actor,
            "duration_ms": duration_ms,
            "details": sanitize_audit_value(deepcopy(details or {})),
        }
        # Frontend metadata and exception text require the same protection as details.
        record = sanitize_audit_value(record)
        self._events.append(record)
        self._events = self._events[-MAX_EVENTS:]
        self._store.async_delay_save(lambda: {"events": self._events}, 2.0)
        return deepcopy(record)

    async def async_sanitize_existing(self, *, apply: bool = False) -> dict[str, int | bool]:
        """Preview or apply secret redaction without deleting audit events."""
        await self.async_load()
        sanitized_events: list[dict[str, Any]] = []
        changed = 0
        for item in self._events:
            sanitized = sanitize_audit_value(deepcopy(item))
            if sanitized != item:
                changed += 1
            sanitized_events.append(sanitized)
        if apply and changed:
            self._events = sanitized_events[-MAX_EVENTS:]
            await self._store.async_save({"events": self._events})
        return {
            "scanned": len(self._events),
            "changed": changed,
            "applied": bool(apply),
            "events_deleted": 0,
        }

    async def async_list(
        self,
        *,
        limit: int = 500,
        component: str | None = None,
        categories: str | Iterable[str] | None = None,
        job_id: str | None = None,
        printer_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        await self.async_load()
        items = self._events
        selected_categories = _normalized_categories(categories)
        if component:
            items = [item for item in items if item.get("component") == component]
        if selected_categories:
            items = [
                item for item in items
                if str(item.get("category", "System")).casefold() in selected_categories
            ]
        if job_id:
            items = [item for item in items if item.get("job_id") == job_id]
        if printer_id:
            items = [item for item in items if item.get("printer_id") == printer_id]
        if status:
            items = [item for item in items if item.get("status") == status]
        bounded = max(1, min(int(limit), MAX_RETURNED_EVENTS))
        # Protect historical records on read without changing stored history or its length.
        return [sanitize_audit_value(deepcopy(item)) for item in items[-bounded:][::-1]]

    async def async_summary(self) -> dict[str, Any]:
        await self.async_load()
        categories = Counter(sanitize_audit_value(str(item.get("category") or "System")) for item in self._events)
        statuses = Counter(sanitize_audit_value(str(item.get("status") or "info")) for item in self._events)
        return {
            "total": len(self._events),
            "maximum": MAX_EVENTS,
            "categories": [
                {"name": name, "count": count}
                for name, count in sorted(categories.items(), key=lambda item: item[0].casefold())
            ],
            "statuses": dict(statuses),
        }

    async def async_clear(self) -> None:
        await self.async_load()
        self._events = []
        await self._store.async_save({"events": []})


def get_audit_log(hass: HomeAssistant) -> StudioAuditLog:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.get(DATA_AUDIT_LOG)
    if not isinstance(runtime, StudioAuditLog):
        runtime = StudioAuditLog(hass)
        data[DATA_AUDIT_LOG] = runtime
    return runtime
