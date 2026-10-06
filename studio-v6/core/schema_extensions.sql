CREATE TABLE IF NOT EXISTS upload_sessions (
    id TEXT PRIMARY KEY,
    original_name TEXT NOT NULL,
    expected_size INTEGER NOT NULL CHECK (expected_size >= 0),
    received_size INTEGER NOT NULL DEFAULT 0 CHECK (received_size >= 0),
    chunk_size INTEGER NOT NULL CHECK (chunk_size > 0),
    source_ui TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    expected_digest TEXT,
    asset_id TEXT REFERENCES assets(id),
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (source_ui IN ('control_center', 'gallery', 'studio'))
);

CREATE TABLE IF NOT EXISTS gallery_folders (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES gallery_folders(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (parent_id, name)
);

CREATE TABLE IF NOT EXISTS gallery_items (
    asset_id TEXT PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    folder_id TEXT REFERENCES gallery_folders(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    favorite INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gallery_tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS gallery_item_tags (
    asset_id TEXT NOT NULL REFERENCES gallery_items(asset_id) ON DELETE CASCADE,
    tag_id TEXT NOT NULL REFERENCES gallery_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (asset_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_upload_sessions_status
ON upload_sessions(status, updated_at);

CREATE INDEX IF NOT EXISTS idx_gallery_items_folder
ON gallery_items(folder_id, title);
