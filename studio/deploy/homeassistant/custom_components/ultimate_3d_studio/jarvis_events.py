"""Stable JARVIS event bridge for Ultimate 3D Studio."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from .models import PrinterSnapshot

EVENT_PRINTER_DISCOVERED = "jarvis_studio_printer_discovered"
EVENT_PRINTER_STATE_CHANGED = "jarvis_studio_printer_state_changed"
EVENT_PRINTER_CONNECTION_CHANGED = "jarvis_studio_printer_connection_changed"
EVENT_PRINT_STARTED = "jarvis_studio_print_started"
EVENT_PRINT_COMPLETED = "jarvis_studio_print_completed"
EVENT_PRINT_FAILED = "jarvis_studio_print_failed"
EVENT_PRINT_PAUSED = "jarvis_studio_print_paused"
EVENT_PRINTER_ISSUES_CHANGED = "jarvis_studio_printer_issues_changed"
EVENT_PRINTER_SNAPSHOT = "jarvis_studio_printer_snapshot"

_PRINTING_STATES = frozenset({"running", "printing", "prepare", "preparing"})
_COMPLETED_STATES = frozenset({"finish", "finished", "completed", "complete"})
_FAILED_STATES = frozenset({"failed", "error", "cancelled", "canceled"})
_PAUSED_STATES = frozenset({"pause", "paused"})


def _normalized_state(value: str | None) -> str:
    return str(value or "unknown").strip().lower() or "unknown"


def _issue_signature(snapshot: PrinterSnapshot) -> tuple[str, ...]:
    values: list[str] = []
    for issue in snapshot.issues:
        if not isinstance(issue, dict):
            continue
        code = str(
            issue.get("code_compact")
            or issue.get("code")
            or issue.get("message")
            or ""
        ).strip()
        if code:
            values.append(code)
    return tuple(sorted(set(values)))


def _event_payload(snapshot: PrinterSnapshot) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "ultimate_3d_studio",
        "printer_id": snapshot.printer_id,
        "name": snapshot.name,
        "provider": snapshot.provider,
        "model": snapshot.model,
        "serial": snapshot.serial,
        "connection_state": snapshot.connection_state,
        "printer_state": snapshot.printer_state,
        "progress": snapshot.progress,
        "current_file": snapshot.current_file,
        "remaining_time_minutes": snapshot.remaining_time_minutes,
        "current_layer": snapshot.current_layer,
        "total_layers": snapshot.total_layers,
        "print_stage_code": snapshot.print_stage_code,
        "print_stage_key": snapshot.print_stage_key,
        "print_stage_label": snapshot.print_stage_label,
        "error_code": snapshot.error_code,
        "error_message": snapshot.error_message,
        "issue_count": len(snapshot.issues),
        "issues": [dict(item) for item in snapshot.issues],
        "updated_at": snapshot.updated_at,
    }


@dataclass(frozen=True, slots=True)
class _ObservedPrinter:
    connection_state: str
    printer_state: str
    current_file: str | None
    error_code: int | str | None
    issues: tuple[str, ...]

    @classmethod
    def from_snapshot(cls, snapshot: PrinterSnapshot) -> "_ObservedPrinter":
        return cls(
            connection_state=_normalized_state(snapshot.connection_state),
            printer_state=_normalized_state(snapshot.printer_state),
            current_file=snapshot.current_file,
            error_code=snapshot.error_code,
            issues=_issue_signature(snapshot),
        )


class JarvisEventBridge:
    """Publish meaningful Studio state transitions to the HA event bus once."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._previous: dict[str, _ObservedPrinter] = {}

    def reset(self) -> None:
        self._previous.clear()

    def observe(self, snapshots: tuple[PrinterSnapshot, ...]) -> None:
        for snapshot in snapshots:
            self._observe_snapshot(snapshot)

    def _fire(
        self,
        event_type: str,
        snapshot: PrinterSnapshot,
        **changes: Any,
    ) -> None:
        payload = _event_payload(snapshot)
        if changes:
            payload["changes"] = changes
        self._hass.bus.async_fire(event_type, payload)

    def _observe_snapshot(self, snapshot: PrinterSnapshot) -> None:
        current = _ObservedPrinter.from_snapshot(snapshot)
        previous = self._previous.get(snapshot.printer_id)
        self._previous[snapshot.printer_id] = current

        if previous is None:
            self._fire(EVENT_PRINTER_DISCOVERED, snapshot)
            self._fire(EVENT_PRINTER_SNAPSHOT, snapshot)
            return

        changed = False

        if previous.connection_state != current.connection_state:
            changed = True
            self._fire(
                EVENT_PRINTER_CONNECTION_CHANGED,
                snapshot,
                previous=previous.connection_state,
                current=current.connection_state,
            )

        if previous.printer_state != current.printer_state:
            changed = True
            self._fire(
                EVENT_PRINTER_STATE_CHANGED,
                snapshot,
                previous=previous.printer_state,
                current=current.printer_state,
            )
            self._fire_lifecycle_event(previous, current, snapshot)

        if (
            previous.issues != current.issues
            or previous.error_code != current.error_code
        ):
            changed = True
            self._fire(
                EVENT_PRINTER_ISSUES_CHANGED,
                snapshot,
                previous=list(previous.issues),
                current=list(current.issues),
                previous_error_code=previous.error_code,
                current_error_code=current.error_code,
            )

        if previous.current_file != current.current_file:
            changed = True

        if changed:
            self._fire(EVENT_PRINTER_SNAPSHOT, snapshot)

    def _fire_lifecycle_event(
        self,
        previous: _ObservedPrinter,
        current: _ObservedPrinter,
        snapshot: PrinterSnapshot,
    ) -> None:
        was_printing = previous.printer_state in _PRINTING_STATES
        is_printing = current.printer_state in _PRINTING_STATES

        if is_printing and not was_printing:
            self._fire(EVENT_PRINT_STARTED, snapshot)
            return
        if current.printer_state in _COMPLETED_STATES and was_printing:
            self._fire(EVENT_PRINT_COMPLETED, snapshot)
            return
        if current.printer_state in _FAILED_STATES and (
            was_printing or previous.printer_state in _PAUSED_STATES
        ):
            self._fire(EVENT_PRINT_FAILED, snapshot)
            return
        if current.printer_state in _PAUSED_STATES and previous.printer_state not in _PAUSED_STATES:
            self._fire(EVENT_PRINT_PAUSED, snapshot)
