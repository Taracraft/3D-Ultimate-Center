import sqlite3

from core.assets import AssetFormat, AssetKind, AssetRecord
from core.database import initialize
from core.makerworld import MakerWorldCreator, MakerWorldModel, MakerWorldPrintProfile
from core.makerworld_repository import MakerWorldRepository
from core.sqlite_assets import SqliteAssetRepository


def test_makerworld_asset_provenance_roundtrip(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    asset = AssetRecord(
        id="asset_mw",
        kind=AssetKind.MODEL,
        format=AssetFormat.THREE_MF,
        digest="9" * 64,
        size_bytes=100,
        original_name="model.3mf",
        storage_key="sha256/99/model",
        created_at="2026-07-01T00:00:00Z",
    )
    SqliteAssetRepository(connection).add(asset)

    model = MakerWorldModel(
        id="mw_1",
        title="MakerWorld Model",
        model_url="https://makerworld.example/models/1",
        description="Description",
        creator=MakerWorldCreator(id="creator_1", name="Creator"),
        license_name="CC BY",
        license_url=None,
        thumbnail_url="https://makerworld.example/thumb.jpg",
        downloads=10,
        likes=5,
        tags=("tag",),
        print_profiles=(
            MakerWorldPrintProfile(
                id="profile_1",
                name="0.20 Standard",
                printer_model="X1 Carbon",
                nozzle_diameter=0.4,
                plate_count=1,
                filament_count=1,
            ),
        ),
    )

    repository = MakerWorldRepository(connection)
    repository.save_model(model, "2026-07-01T00:00:00Z")
    repository.save_import(
        import_id="import_1",
        model_id=model.id,
        profile_id="profile_1",
        selected_profile={
            "id": "profile_1",
            "name": "0.20 Standard",
            "printer_model": "X1 Carbon",
            "nozzle_diameter": 0.4,
            "plate_count": 1,
            "filament_count": 1,
            "thumbnail_url": None,
        },
        destination="gallery",
        source_url=model.model_url,
        created_at="2026-07-01T00:00:00Z",
        license_acknowledged=True,
        asset_id=asset.id,
    )

    info = repository.get_asset_info(asset.id)
    assert info is not None
    assert info["model"]["title"] == "MakerWorld Model"
    assert info["selected_profile_id"] == "profile_1"
    assert info["selected_profile"]["nozzle_diameter"] == 0.4
    assert repository.has_asset_link(asset.id) is True
    assert repository.has_asset_link("asset_other") is False
