import sqlite3

from core.assets import AssetFormat, AssetKind, AssetRecord
from core.database import initialize
from core.handoff import HandoffService
from core.project_service import ProjectService
from core.queue import QueueItemRecord, QueueItemStatus
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_projects import SqliteProjectRepository
from core.sqlite_queue import SqliteQueueRepository


def _setup(tmp_path):
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    assets = SqliteAssetRepository(connection)
    queues = SqliteQueueRepository(connection)
    projects = ProjectService(SqliteProjectRepository(connection))
    handoff = HandoffService(connection, assets, queues, projects)
    return connection, assets, queues, handoff


def _asset() -> AssetRecord:
    return AssetRecord(
        id="asset_model",
        kind=AssetKind.MODEL,
        format=AssetFormat.THREE_MF,
        digest="c" * 64,
        size_bytes=200,
        original_name="model.3mf",
        storage_key="sha256/cc/model",
        created_at="2026-07-01T00:00:00Z",
    )


def test_gallery_asset_opens_in_new_project(tmp_path) -> None:
    _, assets, _, handoff = _setup(tmp_path)
    assets.add(_asset())

    session, record = handoff.gallery_asset_to_project("asset_model")

    assert session.project.name == "model"
    assert session.project.plates[0].objects[0].asset_id == "asset_model"
    assert record.source_kind == "gallery_asset"
    assert record.target_project_id == session.project.id


def test_queue_asset_opens_in_studio(tmp_path) -> None:
    _, assets, queues, handoff = _setup(tmp_path)
    assets.add(_asset())
    queues.save(
        QueueItemRecord(
            id="queue_model",
            printer_serial="SERIAL",
            status=QueueItemStatus.PLANNED,
            quantity=1,
            priority=100,
            created_at="2026-07-01T00:00:00Z",
            updated_at="2026-07-01T00:00:00Z",
            source_kind="asset",
            source_ref="asset_model",
        )
    )

    session, record = handoff.queue_item_to_project("queue_model")

    assert session.project.plates[0].objects[0].asset_id == "asset_model"
    assert record.source_kind == "queue_item"
    assert record.source_ref == "queue_model"
