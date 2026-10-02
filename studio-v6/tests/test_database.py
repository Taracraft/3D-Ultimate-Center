import sqlite3

from core.database import initialize, schema_version


def test_initialize_creates_all_tables(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "assets",
        "projects",
        "plates",
        "plate_geometry",
        "scene_objects",
        "object_geometry",
        "mesh_metadata",
        "preview_jobs",
        "project_revisions",
        "project_handoffs",
        "profiles",
        "slice_jobs",
        "slice_artifacts",
        "gcode_metadata",
        "gcode_layers",
        "queue_items",
        "upload_sessions",
        "gallery_folders",
        "gallery_items",
        "gallery_tags",
        "gallery_item_tags",
        "makerworld_models",
        "makerworld_imports",
        "makerworld_asset_links",
    }.issubset(tables)
    assert schema_version(database) == 8