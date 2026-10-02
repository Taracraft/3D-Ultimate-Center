"""Post-upload analysis and preview scheduling pipeline."""

from __future__ import annotations

from dataclasses import asdict

from .analysis_service import AnalysisService
from .common import utc_now
from .event_bus import EventBus
from .events import StudioEvent
from .job_runner import BackgroundJobRunner, JobRequest
from .preview_service import PreviewService


class PostUploadPipeline:
    def __init__(
        self,
        analysis: AnalysisService,
        previews: PreviewService,
        jobs: BackgroundJobRunner,
        events: EventBus,
    ) -> None:
        self._analysis = analysis
        self._previews = previews
        self._jobs = jobs
        self._events = events
        self._sequence = 0

    async def schedule(self, asset_id: str) -> None:
        await self._jobs.submit(
            JobRequest(
                id=f"analysis:{asset_id}",
                handler=lambda: self._run(asset_id),
            )
        )

    async def _run(self, asset_id: str) -> None:
        await self._publish("asset.analysis.started", {"asset_id": asset_id})
        metadata = await self._to_thread(self._analysis.analyze_asset, asset_id)
        await self._publish(
            "asset.analysis.completed",
            {"asset_id": asset_id, "metadata": asdict(metadata)},
        )

        preview_job = self._previews.create(asset_id)
        await self._publish(
            "asset.preview.queued",
            {"asset_id": asset_id, "job_id": preview_job.id},
        )
        try:
            completed = await self._previews.run(preview_job.id)
            await self._publish(
                "asset.preview.ready",
                {
                    "asset_id": asset_id,
                    "job_id": completed.id,
                    "preview_asset_id": completed.preview_asset_id,
                },
            )
        except Exception as error:
            await self._publish(
                "asset.preview.failed",
                {
                    "asset_id": asset_id,
                    "job_id": preview_job.id,
                    "error": str(error),
                },
            )

    async def _publish(self, topic: str, payload: dict) -> None:
        self._sequence += 1
        await self._events.publish(
            StudioEvent(
                topic=topic,
                sequence=self._sequence,
                timestamp=utc_now(),
                payload=payload,
            )
        )

    @staticmethod
    async def _to_thread(function, *args):
        import asyncio

        return await asyncio.to_thread(function, *args)