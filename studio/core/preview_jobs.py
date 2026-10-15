"""Preview worker job contracts."""

from dataclasses import dataclass
from enum import StrEnum


class PreviewJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True, frozen=True)
class PreviewJobRecord:
    id: str
    asset_id: str
    status: PreviewJobStatus
    progress: float
    created_at: str
    updated_at: str
    preview_asset_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
