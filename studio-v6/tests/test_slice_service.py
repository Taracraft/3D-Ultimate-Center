import asyncio
import sqlite3
from dataclasses import replace

from core.database import initialize
from core.event_bus import EventBus
from core.profiles import ProfileSelection
from core.providers import ProviderCapabilities, ProviderHealth
from core.slice_service import SliceService
from core.slicing import SliceJobRecord, SliceJobStatus
from core.sqlite_slicing import SqliteSliceArtifactRepository, SqliteSliceJobRepository


class FakeProvider:
    async def health(self) -> ProviderHealth:
        return ProviderHealth(provider_id="fake", available=True)

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id="fake",
            input_formats=("stl",),
            output_formats=("gcode",),
            supports_cancel=True,
            supports_layer_preview=True,
            max_parallel_jobs=1,
        )

    async def submit(self, job: SliceJobRecord) -> SliceJobRecord:
        return replace(job, status=SliceJobStatus.SUCCEEDED, progress=100.0)

    async def inspect(self, job_id: str) -> SliceJobRecord:
        raise NotImplementedError

    async def cancel(self, job_id: str) -> None:
        return None


async def test_slice_job_persists_and_emits_events(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    with connection:
        connection.execute(
            "INSERT INTO projects (id, name, revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("project_test", "Test", 1, "2026-07-01T00:00:00Z", "2026-07-01T00:00:00Z"),
        )
        connection.execute(
            "INSERT INTO plates (id, project_id, name, order_index) VALUES (?, ?, ?, ?)",
            ("plate_test", "project_test", "Plate 1", 0),
        )

    events = EventBus()
    service = SliceService(
        SqliteSliceJobRepository(connection),
        SqliteSliceArtifactRepository(connection),
        events,
    )
    service.register_provider("fake", FakeProvider())

    stream = events.subscribe("slicing.job.updated")
    first_event = asyncio.create_task(anext(stream))
    second_event = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)

    job = service.create_job(
        project_id="project_test",
        plate_id="plate_test",
        provider_id="fake",
        profile_selection=ProfileSelection(),
    )
    completed = await service.run(job.id)

    assert completed.status == SliceJobStatus.SUCCEEDED
    assert service.get(job.id).progress == 100.0
    assert (await first_event).payload["status"] == SliceJobStatus.PREPARING
    assert (await second_event).payload["status"] == SliceJobStatus.SUCCEEDED
    await stream.aclose()
