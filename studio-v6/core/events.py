"""Versioned event contracts for WebSocket and internal buses."""

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class StudioEvent:
    topic: str
    sequence: int
    timestamp: str
    payload: dict[str, Any]
    version: int = 1
    event_type: str = "printer_control_center/event"