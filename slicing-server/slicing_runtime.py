"""Build the persistent slicing runtime."""

from __future__ import annotations

from dataclasses import dataclass

from .event_bus import EventBus
from .slice_service import SliceService
from .sqlite_slicing import SqliteSliceArtifactRepository, SqliteSliceJobRepository


@dataclass(slots=True)
class SlicingRuntime:
    events: EventBus
    service: SliceService


def build_slicing_runtime(connection, events: EventBus | None = None) -> SlicingRuntime:
    event_bus = events or EventBus()
    service = SliceService(
        jobs=SqliteSliceJobRepository(connection),
        artifacts=SqliteSliceArtifactRepository(connection),
        events=event_bus,
    )
    return SlicingRuntime(events=event_bus, service=service)