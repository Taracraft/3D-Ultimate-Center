"""Slicing Core types."""

from dataclasses import dataclass
from enum import StrEnum

from .profiles import ProfileSelection


class SliceJobStatus(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


@dataclass(slots=True, frozen=True)
class SliceJobRecord:
    id: str
    project_id: str
    plate_id: str
    provider_id: str
    status: SliceJobStatus
    progress: float
    profile_selection: ProfileSelection
    created_at: str
    updated_at: str
    artifact_asset_ids: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
