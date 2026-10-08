"""SQLite bootstrap and schema migrations for Studio metadata."""

from __future__ import annotations

import sqlite3
from pathlib import Path

CORE_SCHEMA_FILE = Path(__file__).with_name("schema.sql")
EXTENSION_SCHEMA_FILE = Path(__file__).with_name("schema_extensions.sql")
PROJECT_SCHEMA_FILE = Path(__file__).with_name("schema_projects.sql")
GEOMETRY_SCHEMA_FILE = Path(__file__).with_name("schema_geometry.sql")
MESH_SCHEMA_FILE = Path(__file__).with_name("schema_mesh.sql")
SLICING_SCHEMA_FILE = Path(__file__).with_name("schema_slicing.sql")
MAKERWORLD_SCHEMA_FILE = Path(__file__).with_name("schema_makerworld.sql")
CURRENT_SCHEMA_VERSION = 8


def connect(database_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def initialize(database_path: str | Path) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schemas = (
        CORE_SCHEMA_FILE,
        EXTENSION_SCHEMA_FILE,
        PROJECT_SCHEMA_FILE,
        GEOMETRY_SCHEMA_FILE,
        MESH_SCHEMA_FILE,
        SLICING_SCHEMA_FILE,
        MAKERWORLD_SCHEMA_FILE,
    )

    with connect(path) as connection:
        for schema_file in schemas:
            schema = schema_file.read_text(encoding="utf-8-sig")
            connection.executescript(schema)
        _migrate_existing_database(connection)
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")


def schema_version(database_path: str | Path) -> int:
    with connect(database_path) as connection:
        row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def _migrate_existing_database(connection: sqlite3.Connection) -> None:
    _ensure_column(
        connection,
        "makerworld_imports",
        "selected_profile_json",
        "TEXT",
    )


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {row["name"] for row in rows}
    if column_name not in existing:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )
