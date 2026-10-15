"""Persistent preview job service."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from .common import new_id, utc_now
from .preview_jobs import PreviewJobRecord, PreviewJobStatus
from .sqlite_mesh import SqlitePreviewJobRepository


class PreviewRenderer(Protocol):
    async def render(self, asset_id: str, job_id: str) -> str: ...


class PreviewService:
    def __init__(
        self,
        repository: SqlitePreviewJobRepository,
        renderer: PreviewRenderer,
    ) -> None:
        self._repository = repository
        self._renderer = renderer

    def create(self, asset_id: str) -> PreviewJobRecord:
        now = utc_now()
        job = PreviewJobRecord(
            id=new_id("preview"),
            asset_id=asset_id,
            status=PreviewJobStatus.QUEUED,
            progress=0.0,
            created_at=now,
            updated_at=now,
        )
        self._repository.save(job)
        return job

    async def run(self, job_id: str) -> PreviewJobRecord:
        job = self._required(job_id)
        running = replace(
            job,
            status=PreviewJobStatus.RUNNING,
            progress=5.0,
            updated_at=utc_now(),
            error_code=None,
            error_message=None,
        )
        self._repository.save(running)
        try:
            preview_asset_id = await self._renderer.render(running.asset_id, running.id)
            completed = replace(
                running,
                status=PreviewJobStatus.SUCCEEDED,
                progress=100.0,
                preview_asset_id=preview_asset_id,
                updated_at=utc_now(),
            )
            self._repository.save(completed)
            return completed
        except Exception as error:
            failed = replace(
                running,
                status=PreviewJobStatus.FAILED,
                updated_at=utc_now(),
                error_code=error.__class__.__name__,
                error_message=str(error),
            )
            self._repository.save(failed)
            raise

    def get(self, job_id: str) -> PreviewJobRecord:
        return self._required(job_id)

    def _required(self, job_id: str) -> PreviewJobRecord:
        job = self._repository.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job
