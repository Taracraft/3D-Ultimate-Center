import sqlite3

from core.assets import AssetFormat, AssetKind, AssetRecord
from core.database import initialize
from core.project_service import ProjectService
from core.scene_commands import AddObject, SetObjectColor
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_projects import SqliteProjectRepository
from core.studio import Bounds3D, SceneObject, Vector3


def test_restore_creates_new_revision_from_snapshot(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row

    assets = SqliteAssetRepository(connection)
    repository = SqliteProjectRepository(connection)
    service = ProjectService(repository)

    asset = AssetRecord(
        id="asset_restore",
        kind=AssetKind.MODEL,
        format=AssetFormat.STL,
        digest="e" * 64,
        size_bytes=10,
        original_name="restore.stl",
        storage_key="sha256/ee/restore",
        created_at="2026-07-01T00:00:00Z",
    )
    assets.add(asset)

    session = service.create("Restore")
    plate_id = session.project.plates[0].id
    session.execute(
        AddObject(
            plate_id,
            SceneObject(
                id="object_restore",
                asset_id=asset.id,
                name="Restore",
                bounds=Bounds3D(Vector3(-1, -1, 0), Vector3(1, 1, 2)),
            ),
        )
    )
    saved = session.save()
    saved_revision = saved.revision

    session.execute(SetObjectColor(plate_id, "object_restore", "#ff0000"))
    assert session.project.plates[0].objects[0].color == "#ff0000"

    restored = session.restore_revision(saved_revision)
    assert restored.revision > saved_revision
    assert restored.plates[0].objects[0].color is None
    assert restored.plates[0].objects[0].bounds is not None