from core.assets import AssetFormat, AssetKind, AssetRecord
from core.bootstrap import build_runtime
from core.common import utc_now
from core.paths import StudioPaths
from core.queue import QueueItemRecord, QueueItemStatus
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_queue import SqliteQueueRepository


def test_gallery_and_queue_handoffs_through_application(tmp_path) -> None:
    runtime = build_runtime(StudioPaths(tmp_path / "3D-Studio"))
    try:
        assets = SqliteAssetRepository(runtime.connection)
        queue = SqliteQueueRepository(runtime.connection)
        asset = AssetRecord(
            id="asset_api_model",
            kind=AssetKind.MODEL,
            format=AssetFormat.STL,
            digest="d" * 64,
            size_bytes=42,
            original_name="api-model.stl",
            storage_key="sha256/dd/api-model",
            created_at=utc_now(),
        )
        assets.add(asset)

        gallery_response = runtime.application.gallery_to_studio(asset.id)
        assert gallery_response.error is None
        project_id = gallery_response.data["project"]["id"]
        assert gallery_response.data["project"]["plates"][0]["objects"][0]["asset_id"] == asset.id

        now = utc_now()
        queue.save(
            QueueItemRecord(
                id="queue_api_model",
                printer_serial="SERIAL",
                status=QueueItemStatus.PLANNED,
                quantity=1,
                priority=100,
                created_at=now,
                updated_at=now,
                source_kind="asset",
                source_ref=asset.id,
            )
        )
        queue_response = runtime.application.queue_to_studio(
            "queue_api_model",
            project_id,
        )
        assert queue_response.error is None
        objects = queue_response.data["project"]["plates"][0]["objects"]
        assert len(objects) == 2
        assert all(item["asset_id"] == asset.id for item in objects)
    finally:
        runtime.close()