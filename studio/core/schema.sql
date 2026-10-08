PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    format TEXT NOT NULL,
    digest TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    original_name TEXT NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plates (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    UNIQUE (project_id, order_index)
);

CREATE TABLE IF NOT EXISTS scene_objects (
    id TEXT PRIMARY KEY,
    plate_id TEXT NOT NULL REFERENCES plates(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES assets(id),
    name TEXT NOT NULL,
    transform_json TEXT NOT NULL,
    visible INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 0,
    color TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    vendor_id TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS slice_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    plate_id TEXT NOT NULL REFERENCES plates(id),
    provider_id TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    profile_selection_json TEXT NOT NULL,
    artifact_asset_ids_json TEXT NOT NULL DEFAULT '[]',
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queue_items (
    id TEXT PRIMARY KEY,
    printer_serial TEXT NOT NULL,
    status TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 1),
    priority INTEGER NOT NULL DEFAULT 100,
    source_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    scheduled_for TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(kind);
CREATE INDEX IF NOT EXISTS idx_plates_project ON plates(project_id, order_index);
CREATE INDEX IF NOT EXISTS idx_scene_objects_plate ON scene_objects(plate_id);
CREATE INDEX IF NOT EXISTS idx_profiles_kind ON profiles(kind);
CREATE INDEX IF NOT EXISTS idx_slice_jobs_status ON slice_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_queue_items_status ON queue_items(status, priority, created_at);
