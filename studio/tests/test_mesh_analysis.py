import sqlite3

from core.assets import AssetFormat, AssetKind, AssetRecord
from core.database import initialize
from core.mesh import MeshFace, MeshMetadata
from core.mesh_analysis import choose_flat_placement
from core.mesh_service import MeshService
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_mesh import SqliteMeshRepository
from core.studio import Bounds3D, PlateRecord, ProjectRecord, SceneObject, Vector3


def test_choose_largest_support_face() -> None:
    metadata = MeshMetadata(
        triangle_count=12,
        vertex_count=8,
        bounds=Bounds3D(Vector3(-1, -1, -1), Vector3(1, 1, 1)),
        volume_mm3=8.0,
        manifold=True,
        watertight=True,
        candidate_faces=(
            MeshFace(Vector3(0, 0, 1), 4.0, Vector3(0, 0, 1)),
            MeshFace(Vector3(1, 0, 0), 8.0, Vector3(1, 0, 0)),
        ),
    )
    placement = choose_flat_placement(metadata)
    assert placement.support_area == 8.0
    assert placement.confidence == 8.0 / 12.0


def test_mesh_service_applies_flat_rotation(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row

    assets = SqliteAssetRepository(connection)
    mesh = SqliteMeshRepository(connection)
    asset = AssetRecord(
        id="asset_mesh",
        kind=AssetKind.MODEL,
        format=AssetFormat.STL,
        digest="f" * 64,
        size_bytes=10,
        original_name="mesh.stl",
        storage_key="sha256/ff/mesh",
        created_at="2026-07-01T00:00:00Z",
    )
    assets.add(asset)
    mesh.save(
        asset.id,
        MeshMetadata(
            triangle_count=2,
            vertex_count=4,
            bounds=Bounds3D(Vector3(-1, -1, 0), Vector3(1, 1, 2)),
            volume_mm3=None,
            manifold=None,
            watertight=None,
            candidate_faces=(
                MeshFace(Vector3(0, 1, 0), 10.0, Vector3(0, 1, 0)),
            ),
        ),
        "2026-07-01T00:00:00Z",
    )
    project = ProjectRecord(
        id="project_mesh",
        name="Mesh",
        revision=1,
        plates=(
            PlateRecord(
                id="plate_mesh",
                name="Plate 1",
                order_index=0,
                objects=(SceneObject(id="object_mesh", asset_id=asset.id, name="Mesh"),),
            ),
        ),
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
    )
    flattened = MeshService(mesh).place_object_flat(
        project,
        "plate_mesh",
        "object_mesh",
    )
    assert flattened.plates[0].objects[0].transform.rotation != (0.0, 0.0, 0.0)
