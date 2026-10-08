CREATE TABLE IF NOT EXISTS makerworld_models (
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

CREATE TABLE IF NOT EXISTS makerworld_imports (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    profile_id TEXT,
    destination TEXT NOT NULL,
    asset_id TEXT REFERENCES assets(id),
    project_id TEXT REFERENCES projects(id),
    slice_job_id TEXT REFERENCES slice_jobs(id),
    source_url TEXT NOT NULL,
    license_acknowledged INTEGER NOT NULL DEFAULT 0,
    selected_profile_json TEXT,
    created_at TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    CHECK (destination IN ('gallery', 'studio', 'slicer'))
);

CREATE TABLE IF NOT EXISTS makerworld_asset_links (
    asset_id TEXT PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL REFERENCES makerworld_models(model_id) ON DELETE CASCADE,
    import_id TEXT NOT NULL REFERENCES makerworld_imports(id) ON DELETE CASCADE,
    selected_profile_id TEXT,
    selected_profile_json TEXT,
    linked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_makerworld_imports_model
ON makerworld_imports(model_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_makerworld_asset_links_model
ON makerworld_asset_links(model_id, linked_at DESC);
