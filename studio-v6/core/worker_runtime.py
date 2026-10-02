"""Build the optional background worker runtime."""

from __future__ import annotations

from dataclasses import dataclass

from .analysis_service import AnalysisService
from .asset_service import AssetService
from .event_bus import EventBus
from .job_runner import BackgroundJobRunner
from .post_upload_pipeline import PostUploadPipeline
from .preview_service import PreviewRenderer, PreviewService
from .sqlite_assets import SqliteAssetRepository
from .sqlite_mesh import SqliteMeshRepository, SqlitePreviewJobRepository


@dataclass(slots=True)
class WorkerRuntime:
    events: EventBus
    jobs: BackgroundJobRunner
    pipeline: PostUploadPipeline

    async def start(self) -> None:
        await self.jobs.start()

    async def close(self) -> None:
        await self.jobs.close()


def build_worker_runtime(
    *,
    connection,
    asset_service: AssetService,
    renderer: PreviewRenderer,
    max_parallel_jobs: int = 1,
) -> WorkerRuntime:
    mesh_repository = SqliteMeshRepository(connection)
    preview_repository = SqlitePreviewJobRepository(connection)
    analysis = AnalysisService(asset_service, mesh_repository)
    previews = PreviewService(preview_repository, renderer)
    jobs = BackgroundJobRunner(max_parallel_jobs=max_parallel_jobs)
    events = EventBus()
    pipeline = PostUploadPipeline(analysis, previews, jobs, events)
    return WorkerRuntime(events=events, jobs=jobs, pipeline=pipeline)