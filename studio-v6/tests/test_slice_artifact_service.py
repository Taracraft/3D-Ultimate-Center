import sqlite3
from dataclasses import replace

from core.asset_service import AssetService
from core.assets import AssetFormat, AssetKind, AssetRecord
from core.common import utc_now
from core.database import initialize
from core.event_bus import EventBus
from core.gcode_service import GCodeService
from core.profiles import ProfileSelection
from core.slice_artifact_service import SliceArtifactService
from core.slice_artifacts import SliceArtifactKind
from core.slice_service import SliceService
from core.slicing import SliceJobRecord, SliceJobStatus
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_slicing import (
    SqliteGCodeRepository,
    SqliteSliceArtifactRepository,
    SqliteSliceJobRepository,
)


class FakeProvider:
    async def health(self):
        raise NotImplementedError

    async def capabilities(self):
        raise NotImplementedError

    async def submit(self, job: SliceJobRecord) -> SliceJobRecord:
        return replace(job, status=SliceJobStatus.SUCCEEDED, progress=100.0)

    async def inspect(self, job_id: str) -> SliceJobRecord:
        raise NotImplementedError

    async def cancel(self, job_id: str) -> None:
        return None


def test_gcode_artifact_is_registered_and_analyzed(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    now = utc_now()
    with connection:
        connection.execute(
            "INSERT INTO projects (id, name, revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("project_artifact", "Artifact", 1, now, now),
        )
        connection.execute(
            "INSERT INTO plates (id, project_id, name, order_index) VALUES (?, ?, ?, ?)",
            ("plate_artifact", "project_artifact", "Plate 1", 0),
        )

    asset_repository = SqliteAssetRepository(connection)
    assets = AssetService(asset_repository, tmp_path / "assets")
    jobs = SqliteSliceJobRepository(connection)
    artifacts = SqliteSliceArtifactRepository(connection)
    slicing = SliceService(jobs, artifacts, EventBus())
    slicing.register_provider("fake", FakeProvider())
    job = slicing.create_job(
        project_id="project_artifact",
        plate_id="plate_artifact",
        provider_id="fake",
        profile_selection=ProfileSelection(),
    )

    gcode_file = tmp_path / "output.gcode"
    gcode_file.write_text(
        ";LAYER:0\nG1 X0 Y0 Z0.2\nG1 X10 Y10 E1\n",
        encoding="utf-8",
    )
    gcode_repository = SqliteGCodeRepository(connection)
    service = SliceArtifactService(
        assets,
        slicing,
        GCodeService(assets, gcode_repository),
    )
    result = service.register_file(
        job_id=job.id,
        source_path=gcode_file,
        original_name="output.gcode",
        kind=SliceArtifactKind.GCODE,
    )

    assert result["asset"].format == AssetFormat.GCODE
    assert result["artifact"].asset_id in result["job"].artifact_asset_ids
    assert result["gcode_metadata"].layer_count == 1
    assert gcode_repository.get(result["asset"].id) is not None
