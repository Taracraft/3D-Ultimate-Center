"""Queue Core types."""

from dataclasses import dataclass
from enum import StrEnum


class QueueItemStatus(StrEnum):
    PLANNED = "planned"
    READY = "ready"
    PRINTING = "printing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True, frozen=True)
class QueueItemRecord:
    id: str
    printer_serial: str
    status: QueueItemStatus
    quantity: int
    priority: int
    created_at: str
    updated_at: str
    source_ref: str
    source_kind: str
    scheduled_for: str | None = None
