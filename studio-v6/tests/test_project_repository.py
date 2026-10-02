import sqlite3

from core.assets import AssetFormat, AssetKind, AssetRecord
from core.database import initialize
from core.project_service import ProjectService
from core.scene_commands import AddObject, SetObjectColor, SetObjectTransform
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_projects import SqliteProjectRepository
from core.studio import SceneObject, Transform3D


def test_project_roundtrip_with_revision(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row

    assets = SqliteAssetRepository(connection)
    projects = SqliteProjectRepository(connection)
    service = ProjectService(projects)

    asset = AssetRecord(
        id="asset_cube",
        kind=AssetKind.MODEL,
        format=AssetFormat.STL,
        digest="b" * 64,
        size_bytes=100,
        original_name="cube.stl",
        storage_key="sha256/bb/cube",
        created_at="2026-07-01T00:00:00Z",
    )
    assets.add(asset)

    session = service.create("Calibration")
    plate_id = session.project.plates[0].id
    scene_object = SceneObject(
        id="object_cube",
        asset_id=asset.id,
        name="Cube",
    )
    session.execute(AddObject(plate_id, scene_object))
    session.execute(
        SetObjectTransform(
            plate_id,
            scene_object.id,
            Transform3D(position=(5.0, 6.0, 0.0), scale=(2.0, 2.0, 2.0)),
        )
    )
    session.execute(SetObjectColor(plate_id, scene_object.id, "#00ffaa"))
    saved = session.save()

    reopened = service.open(saved.id).project
    loaded_object = reopened.plates[0].objects[0]

    assert reopened.revision == 4
    assert loaded_object.transform.position == (5.0, 6.0, 0.0)
    assert loaded_object.transform.scale == (2.0, 2.0, 2.0)
    assert loaded_object.color == "#00ffaa"
    assert projects.latest_snapshot(saved.id) is not None
