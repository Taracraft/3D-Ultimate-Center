import sqlite3

from core.assets import AssetFormat, AssetKind, AssetRecord
from core.database import initialize
from core.preview_jobs import PreviewJobStatus
from core.preview_service import PreviewService
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_mesh import SqlitePreviewJobRepository


class FakeRenderer:
    async def render(self, asset_id: str, job_id: str) -> str:
        assert asset_id == "asset_preview_source"
        assert job_id.startswith("preview_")
        return "asset_preview_png"


async def test_preview_job_success(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row

    assets = SqliteAssetRepository(connection)
    assets.add(
        AssetRecord(
            id="asset_preview_source",
            kind=AssetKind.MODEL,
            format=AssetFormat.STL,
            digest="1" * 64,
            size_bytes=10,
            original_name="source.stl",
            storage_key="sha256/11/source",
            created_at="2026-07-01T00:00:00Z",
        )
    )
    assets.add(
        AssetRecord(
            id="asset_preview_png",
            kind=AssetKind.PREVIEW,
            format=AssetFormat.PNG,
            digest="2" * 64,
            size_bytes=5,
            original_name="preview.png",
            storage_key="sha256/22/preview",
            created_at="2026-07-01T00:00:00Z",
        )
    )

    service = PreviewService(SqlitePreviewJobRepository(connection), FakeRenderer())
    job = service.create("asset_preview_source")
    completed = await service.run(job.id)

    assert completed.status == PreviewJobStatus.SUCCEEDED
    assert completed.progress == 100.0
    assert completed.preview_asset_id == "asset_preview_png"
