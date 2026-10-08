"""Persistent print-job journal and repeat queue for Ultimate 3D Studio."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import PrinterSnapshot

STORE_VERSION = 1
MAX_HISTORY = 100
MAX_QUEUE = 100
ACTIVE_STATES = {"running", "printing", "pause", "paused", "prepare", "preparing"}
SUCCESS_STATES = {"finish", "finished", "complete", "completed"}
IDLE_STATES = {"idle"}
FAILED_STATES = {"failed", "error", "fault"}
CANCELLED_STATES = {"abort", "aborted", "cancel", "cancelled", "canceled", "stopped"}
TERMINAL_STATES = SUCCESS_STATES | IDLE_STATES | FAILED_STATES | CANCELLED_STATES


class JobHistory:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store(hass, STORE_VERSION, f"ultimate_3d_studio.{entry_id}.jobs")
        self._history: list[dict[str, Any]] = []
        self._current: dict[str, dict[str, Any]] = {}
        self._queue: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self._history = stored.get("history", []) if isinstance(stored.get("history", []), list) else []
        self._current = stored.get("current", {}) if isinstance(stored.get("current", {}), dict) else {}
        self._queue = stored.get("queue", []) if isinstance(stored.get("queue", []), list) else []

    async def async_observe(self, snapshots: tuple[PrinterSnapshot, ...]) -> None:
        changed = False
        now = datetime.now(UTC).isoformat()

        for snapshot in snapshots:
            printer_id = str(getattr(snapshot, "printer_id", ""))
            if not printer_id:
                continue
            state = str(getattr(snapshot, "printer_state", None) or "unknown").strip().lower()
            current = self._current.get(printer_id)
            file_name = str(getattr(snapshot, "current_file", None) or "Unbenannter Druckauftrag")

            if state in ACTIVE_STATES:
                if current is None or current.get("file") != file_name:
                    if current is not None:
                        self._finish(current, "replaced", now)
                    current = self._new_job(snapshot, file_name, state, now)
                    queued = self._take_matching_queue_item(printer_id, file_name)
                    if queued is not None:
                        current["queue_job_id"] = queued.get("job_id")
                        current["source_job_id"] = queued.get("source_job_id")
                    self._current[printer_id] = current
                else:
                    self._update_job(current, snapshot, state, now)
                changed = True
                continue

            if current is not None and state in TERMINAL_STATES:
                self._update_terminal_job(current, snapshot, state, now)
                self._finish(current, self._terminal_result(state, snapshot), now)
                self._current.pop(printer_id, None)
                changed = True

        if changed:
            await self._save()

    @staticmethod
    def _terminal_result(state: str, snapshot: PrinterSnapshot) -> str:
        if state in FAILED_STATES:
            return "failed"
        if state in CANCELLED_STATES:
            return "cancelled"
        if state in SUCCESS_STATES:
            return "completed"
        try:
            progress = float(getattr(snapshot, "progress", None) or 0)
        except (TypeError, ValueError):
            progress = 0
        return "completed" if progress >= 99 else "stopped"

    async def async_repeat(self, job_id: str) -> dict[str, Any] | None:
        source = next((item for item in self._history if str(item.get("job_id", "")) == job_id), None)
        if source is None:
            return None
        now = datetime.now(UTC).isoformat()
        queued = deepcopy(source)
        queued.update({
            "job_id": f"queue:{uuid4().hex}",
            "source_job_id": job_id,
            "status": "queued",
            "progress": 0,
            "queued_at": now,
            "started_at": None,
            "updated_at": now,
            "completed_at": None,
            "duration_seconds": None,
            "current_layer": None,
            "remaining_time_minutes": None,
        })
        self._queue.insert(0, queued)
        del self._queue[MAX_QUEUE:]
        await self._save()
        return deepcopy(queued)

    async def async_remove_queued(self, job_id: str) -> dict[str, Any] | None:
        for index, item in enumerate(self._queue):
            if str(item.get("job_id", "")) == job_id:
                removed = self._queue.pop(index)
                await self._save()
                return deepcopy(removed)
        return None

    def _take_matching_queue_item(self, printer_id: str, file_name: str) -> dict[str, Any] | None:
        for index, item in enumerate(self._queue):
            if str(item.get("file", "")) == file_name and str(item.get("printer_id", "")) in {"", printer_id}:
                return self._queue.pop(index)
        return None

    @staticmethod
    def _value(snapshot: PrinterSnapshot, name: str, default: Any = None) -> Any:
        return getattr(snapshot, name, default)

    @classmethod
    def _new_job(cls, snapshot: PrinterSnapshot, file_name: str, state: str, now: str) -> dict[str, Any]:
        printer_id = str(cls._value(snapshot, "printer_id", ""))
        return {
            "job_id": f"{printer_id}:{now}",
            "printer_id": printer_id,
            "printer_name": cls._value(snapshot, "name", printer_id),
            "file": file_name,
            "status": "paused" if state in {"pause", "paused"} else "running",
            "progress": cls._value(snapshot, "progress"),
            "started_at": now,
            "updated_at": cls._value(snapshot, "updated_at") or now,
            "completed_at": None,
            "duration_seconds": None,
            "start_layer": cls._value(snapshot, "current_layer"),
            "current_layer": cls._value(snapshot, "current_layer"),
            "total_layers": cls._value(snapshot, "total_layers"),
            "remaining_time_minutes": cls._value(snapshot, "remaining_time_minutes"),
            "speed_level": cls._value(snapshot, "speed_level"),
            "nozzle_temperature": cls._value(snapshot, "nozzle_temperature"),
            "nozzle_target_temperature": cls._value(snapshot, "nozzle_target_temperature"),
            "bed_temperature": cls._value(snapshot, "bed_temperature"),
            "bed_target_temperature": cls._value(snapshot, "bed_target_temperature"),
        }

    @classmethod
    def _update_job(cls, current: dict[str, Any], snapshot: PrinterSnapshot, state: str, now: str) -> None:
        current["status"] = "paused" if state in {"pause", "paused"} else "running"
        cls._update_metrics(current, snapshot, now)

    @classmethod
    def _update_terminal_job(cls, current: dict[str, Any], snapshot: PrinterSnapshot, state: str, now: str) -> None:
        current["printer_terminal_state"] = state
        cls._update_metrics(current, snapshot, now)

    @classmethod
    def _update_metrics(cls, current: dict[str, Any], snapshot: PrinterSnapshot, now: str) -> None:
        for name in (
            "progress", "current_layer", "total_layers", "remaining_time_minutes",
            "speed_level", "nozzle_temperature", "nozzle_target_temperature",
            "bed_temperature", "bed_target_temperature",
        ):
            current[name] = cls._value(snapshot, name)
        current["updated_at"] = cls._value(snapshot, "updated_at") or now

    def _finish(self, job: dict[str, Any], status: str, completed_at: str) -> None:
        finished = deepcopy(job)
        finished["status"] = status
        finished["completed_at"] = completed_at
        finished["progress"] = 100 if status == "completed" else finished.get("progress")
        finished["duration_seconds"] = self._duration_seconds(finished.get("started_at"), completed_at)
        self._history.insert(0, finished)
        del self._history[MAX_HISTORY:]

    @staticmethod
    def _duration_seconds(started_at: Any, completed_at: Any) -> int | None:
        if not started_at or not completed_at:
            return None
        try:
            started = datetime.fromisoformat(str(started_at))
            completed = datetime.fromisoformat(str(completed_at))
        except (TypeError, ValueError):
            return None
        return max(0, int((completed - started).total_seconds()))

    async def _save(self) -> None:
        await self._store.async_save({"history": self._history, "current": self._current, "queue": self._queue})

    def as_dict(self) -> dict[str, Any]:
        current = sorted(
            (deepcopy(item) for item in self._current.values()),
            key=lambda item: item.get("started_at", ""),
            reverse=True,
        )
        return {
            "current": current,
            "queue": deepcopy(self._queue),
            "history": deepcopy(self._history),
            "current_count": len(current),
            "queue_count": len(self._queue),
            "history_count": len(self._history),
            "persistent": True,
            "read_only": False,
            "repeat_supported": True,
            "queue_remove_supported": True,
            "queue_execution_enabled": False,
        }
