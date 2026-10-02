import sqlite3

from core.database import initialize, schema_version


def test_schema_7_makerworld_imports_migrates_to_schema_8(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE makerworld_imports (
            id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            profile_id TEXT,
            destination TEXT NOT NULL,
            asset_id TEXT,
            project_id TEXT,
            slice_job_id TEXT,
            source_url TEXT NOT NULL,
            license_acknowledged INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            error_code TEXT,
            error_message TEXT
        );
        PRAGMA user_version = 7;
        """
    )
    connection.close()

    initialize(database)

    connection = sqlite3.connect(database)
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(makerworld_imports)")
    }
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    connection.close()

    assert "selected_profile_json" in columns
    assert "makerworld_asset_links" in tables
    assert schema_version(database) == 8