import sqlite3

from core.database import initialize, schema_version


def test_v7_database_is_migrated_to_v8(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE assets (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            format TEXT NOT NULL,
            digest TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            storage_key TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            revision INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE slice_jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            plate_id TEXT,
            provider_id TEXT NOT NULL,
            status TEXT NOT NULL,
            progress REAL NOT NULL,
            profile_selection_json TEXT NOT NULL,
            artifact_asset_ids_json TEXT NOT NULL,
            error_code TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE makerworld_models (
            model_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            model_url TEXT NOT NULL,
            creator_id TEXT,
            creator_name TEXT NOT NULL,
            license_name TEXT,
            license_url TEXT,
            thumbnail_url TEXT,
            metadata_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
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
