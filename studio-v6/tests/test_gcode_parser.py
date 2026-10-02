import sqlite3

from core.assets import AssetFormat, AssetKind, AssetRecord
from core.database import initialize
from core.gcode_parser import parse_gcode
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_slicing import SqliteGCodeRepository


def test_gcode_parser_extracts_layers_moves_and_bounds(tmp_path) -> None:
    path = tmp_path / "cube.gcode"
    path.write_text(
        "\n".join(
            (
                ";TIME:120",
                ";Filament used: 2.5m",
                "M82",
                ";LAYER:0",
                "G1 X0 Y0 Z0.2 F6000",
                "G1 X10 Y0 E1.0 F1200",
                "G1 X10 Y10 E2.0",
                ";LAYER:1",
                "G1 X0 Y10 Z0.4 F6000",
                "G1 X0 Y0 E3.0",
            )
        ),
        encoding="utf-8",
    )
    metadata = parse_gcode(path)

    assert metadata.layer_count == 2
    assert metadata.estimated_time_seconds == 120.0
    assert metadata.filament_mm == 2500.0
    assert metadata.bounds == (0.0, 0.0, 0.2, 10.0, 10.0, 0.4)
    assert metadata.layers[0].extrusion_count == 2
    assert metadata.layers[1].extrusion_count == 1


def test_gcode_metadata_roundtrip(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row

    assets = SqliteAssetRepository(connection)
    repository = SqliteGCodeRepository(connection)
    asset = AssetRecord(
        id="asset_gcode",
        kind=AssetKind.SLICE_ARTIFACT,
        format=AssetFormat.GCODE,
        digest="3" * 64,
        size_bytes=10,
        original_name="cube.gcode",
        storage_key="sha256/33/cube",
        created_at="2026-07-01T00:00:00Z",
    )
    assets.add(asset)

    path = tmp_path / "cube.gcode"
    path.write_text(";LAYER:0\nG1 X1 Y2 Z0.2 E1\n", encoding="utf-8")
    metadata = parse_gcode(path)
    repository.save(asset.id, metadata, "2026-07-01T00:00:00Z")

    loaded = repository.get(asset.id)
    assert loaded == metadata