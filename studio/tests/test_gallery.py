import sqlite3

from core.assets import AssetFormat, AssetKind, AssetRecord
from core.database import initialize
from core.gallery import GalleryItem
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_gallery import SqliteGalleryRepository


def test_gallery_item_roundtrip_and_search(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    assets = SqliteAssetRepository(connection)
    gallery = SqliteGalleryRepository(connection)

    asset = AssetRecord(
        id="asset_cube",
        kind=AssetKind.MODEL,
        format=AssetFormat.STL,
        digest="a" * 64,
        size_bytes=123,
        original_name="cube.stl",
        storage_key="sha256/aa/asset_cube",
        created_at="2026-07-01T00:00:00Z",
    )
    assets.add(asset)

    item = GalleryItem(
        asset_id=asset.id,
        title="Calibration Cube",
        description="Small calibration model",
        favorite=True,
        tags=("calibration", "cube"),
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
    )
    gallery.add_item(item)

    loaded = gallery.get_item(asset.id)
    results = gallery.search("Calibration")

    assert loaded == item
    assert results == [item]
