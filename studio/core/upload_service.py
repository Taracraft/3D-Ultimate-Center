"""Resumable chunk upload service shared by all Studio surfaces."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .common import new_id, utc_now
from .repositories import UploadRepository
from .uploads import UploadSession, UploadStatus

_ALLOWED_SOURCES = {"control_center", "gallery", "studio"}
_ALLOWED_TARGETS = {"gallery", "studio", "queue", "slice", "printer"}


class UploadService:
    def __init__(self, repository: UploadRepository, runtime_root: str | Path) -> None:
        self._repository = repository
        self._runtime_root = Path(runtime_root)

    def create(
        self,
        *,
        original_name: str,
        expected_size: int,
        source_ui: str,
        target: str,
        chunk_size: int = 4 * 1024 * 1024,
        expected_digest: str | None = None,
    ) -> UploadSession:
        if source_ui not in _ALLOWED_SOURCES:
            raise ValueError(f"unsupported source_ui: {source_ui}")
        if target not in _ALLOWED_TARGETS:
            raise ValueError(f"unsupported target: {target}")
        if expected_size < 0:
            raise ValueError("expected_size must not be negative")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")

        now = utc_now()
        session = UploadSession(
            id=new_id("upload"),
            original_name=Path(original_name).name,
            expected_size=expected_size,
            received_size=0,
            chunk_size=chunk_size,
            source_ui=source_ui,
            target=target,
            status=UploadStatus.CREATED,
            created_at=now,
            updated_at=now,
            expected_digest=expected_digest.lower() if expected_digest else None,
        )
        self._repository.save(session)
        return session

    def write_chunk(self, upload_id: str, offset: int, payload: bytes) -> UploadSession:
        session = self._required(upload_id)
        if session.status in {
            UploadStatus.COMPLETED,
            UploadStatus.CANCELLED,
            UploadStatus.FAILED,
        }:
            raise ValueError(f"upload is already {session.status.value}")
        if offset != session.received_size:
            raise ValueError(
                f"unexpected offset {offset}; expected {session.received_size}"
            )
        if len(payload) > session.chunk_size:
            raise ValueError("chunk exceeds configured chunk_size")
        if offset + len(payload) > session.expected_size:
            raise ValueError("chunk exceeds expected upload size")

        path = self.partial_path(session.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "r+b" if path.exists() else "w+b"
        with path.open(mode) as target:
            target.seek(offset)
            target.write(payload)
            target.flush()

        updated = replace(
            session,
            received_size=offset + len(payload),
            status=UploadStatus.RECEIVING,
            updated_at=utc_now(),
        )
        self._repository.save(updated)
        return updated

    def mark_verifying(self, upload_id: str) -> UploadSession:
        session = self._required(upload_id)
        if session.received_size != session.expected_size:
            raise ValueError("upload is incomplete")
        updated = replace(
            session,
            status=UploadStatus.VERIFYING,
            updated_at=utc_now(),
            error_code=None,
            error_message=None,
        )
        self._repository.save(updated)
        return updated

    def mark_completed(self, upload_id: str, asset_id: str) -> UploadSession:
        session = self._required(upload_id)
        updated = replace(
            session,
            status=UploadStatus.COMPLETED,
            asset_id=asset_id,
            updated_at=utc_now(),
            error_code=None,
            error_message=None,
        )
        self._repository.save(updated)
        return updated

    def mark_failed(
        self,
        upload_id: str,
        error_code: str,
        error_message: str,
    ) -> UploadSession:
        session = self._required(upload_id)
        updated = replace(
            session,
            status=UploadStatus.FAILED,
            updated_at=utc_now(),
            error_code=error_code,
            error_message=error_message,
        )
        self._repository.save(updated)
        return updated

    def cancel(self, upload_id: str) -> UploadSession:
        session = self._required(upload_id)
        self.partial_path(upload_id).unlink(missing_ok=True)
        updated = replace(
            session,
            status=UploadStatus.CANCELLED,
            updated_at=utc_now(),
        )
        self._repository.save(updated)
        return updated

    def partial_path(self, upload_id: str) -> Path:
        return self._runtime_root / "uploads" / f"{upload_id}.part"

    def _required(self, upload_id: str) -> UploadSession:
        session = self._repository.get(upload_id)
        if session is None:
            raise KeyError(upload_id)
        return session
