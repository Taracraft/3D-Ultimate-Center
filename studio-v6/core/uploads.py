"""Unified upload session contracts."""

from dataclasses import dataclass
from enum import StrEnum


class UploadStatus(StrEnum):
    CREATED = "created"
    RECEIVING = "receiving"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True, frozen=True)
class UploadSession:
    id: str
    original_name: str
    expected_size: int
    received_size: int
    chunk_size: int
    source_ui: str
    target: str
    status: UploadStatus
    created_at: str
    updated_at: str
    expected_digest: str | None = None
    asset_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def progress(self) -> float:
        if self.expected_size <= 0:
            return 0.0
        return min(100.0, (self.received_size / self.expected_size) * 100.0)