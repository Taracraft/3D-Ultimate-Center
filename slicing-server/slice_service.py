"""Persistent slice job orchestration and event publication."""

from __future__ import annotations

from dataclasses import asdict, replace

from .common import new_id, utc_now
from .event_bus import EventBus
from .events import StudioEvent
from .profiles import ProfileSelection
from .providers import SlicerProvider
from .slice_artifacts import SliceArtifactRecord
from .slicing import SliceJobRecord, SliceJobStatus
from .sqlite_slicing import SqliteSliceArtifactRepository, SqliteSliceJobRepository


class SliceService:
    def __init__(
        self,
        jobs: SqliteSliceJobRepository,
        artifacts: SqliteSliceArtifactRepository,
        events: EventBus,
    ) -> None:
        self._jobs = jobs
        self._artifacts = artifacts
        self._events = events
        self._providers: dict[str, SlicerProvider] = {}
        self._sequence = 0

    def register_provider(self, provider_id: str, provider: SlicerProvider) -> None:
        if provider_id in self._providers:
            raise ValueError(f"provider already registered: {provider_id}")
        self._providers[provider_id] = provider

    def create_job(
        self,
        *,
        project_id: str,
        plate_id: str,
        provider_id: str,
        profile_selection: ProfileSelection,
    ) -> SliceJobRecord:
        if provider_id not in self._providers:
            raise ValueError(f"unknown slicer provider: {provider_id}")
        now = utc_now()
        job = SliceJobRecord(
            id=new_id("slice"),
            project_id=project_id,
            plate_id=plate_id,
            provider_id=provider_id,
            status=SliceJobStatus.QUEUED,
            progress=0.0,
            profile_selection=profile_selection,
            created_at=now,
            updated_at=now,
        )
        self._jobs.save(job)
        return job

    async def run(self, job_id: str) -> SliceJobRecord:
        job = self._required(job_id)
        provider = self._providers.get(job.provider_id)
        if provider is None:
            raise ValueError(f"provider is not registered: {job.provider_id}")

        preparing = replace(
            job,
            status=SliceJobStatus.PREPARING,
            progress=1.0,
            updated_at=utc_now(),
            error_code=None,
            error_message=None,
        )
        self._jobs.save(preparing)
        await self._publish("slicing.job.updated", preparing)

        try:
            completed = await provider.submit(preparing)
            completed = replace(completed, updated_at=utc_now())
            self._jobs.save(completed)
            await self._publish("slicing.job.updated", completed)
            return completed
        except Exception as error:
            failed = replace(
                preparing,
                status=SliceJobStatus.FAILED,
                updated_at=utc_now(),
                error_code=error.__class__.__name__,
                error_message=str(error),
            )
            self._jobs.save(failed)
            await self._publish("slicing.job.updated", failed)
            raise

    async def cancel(self, job_id: str) -> SliceJobRecord:
        job = self._required(job_id)
        provider = self._providers.get(job.provider_id)
        if provider is None:
            raise ValueError(f"provider is not registered: {job.provider_id}")
        cancelling = replace(
            job,
            status=SliceJobStatus.CANCELLING,
            updated_at=utc_now(),
        )
        self._jobs.save(cancelling)
        await self._publish("slicing.job.updated", cancelling)
        await provider.cancel(job.id)
        cancelled = replace(
            cancelling,
            status=SliceJobStatus.CANCELLED,
            progress=0.0,
            updated_at=utc_now(),
        )
        self._jobs.save(cancelled)
        await self._publish("slicing.job.updated", cancelled)
        return cancelled

    def attach_artifact(self, artifact: SliceArtifactRecord) -> SliceJobRecord:
        job = self._required(artifact.slice_job_id)
        if artifact.asset_id in job.artifact_asset_ids:
            return job
        self._artifacts.add(artifact)
        updated = replace(
            job,
            artifact_asset_ids=job.artifact_asset_ids + (artifact.asset_id,),
            updated_at=utc_now(),
        )
        self._jobs.save(updated)
        return updated

    def get(self, job_id: str) -> SliceJobRecord:
        return self._required(job_id)

    def _required(self, job_id: str) -> SliceJobRecord:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    async def _publish(self, topic: str, job: SliceJobRecord) -> None:
        self._sequence += 1
        await self._events.publish(
            StudioEvent(
                topic=topic,
                sequence=self._sequence,
                timestamp=utc_now(),
                payload=asdict(job),
            )
        )