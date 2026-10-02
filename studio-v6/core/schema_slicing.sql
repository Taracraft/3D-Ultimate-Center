CREATE TABLE IF NOT EXISTS slice_artifacts (
    id TEXT PRIMARY KEY,
    slice_job_id TEXT NOT NULL REFERENCES slice_jobs(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gcode_metadata (
    asset_id TEXT PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    layer_count INTEGER NOT NULL DEFAULT 0 CHECK (layer_count >= 0),
    estimated_time_seconds REAL,
    filament_mm REAL,
    filament_grams REAL,
    filament_cost REAL,
    min_x REAL,
    min_y REAL,
    min_z REAL,
    max_x REAL,
    max_y REAL,
    max_z REAL,
    parsed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gcode_layers (
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    layer_index INTEGER NOT NULL CHECK (layer_index >= 0),
    z_height REAL,
    time_seconds REAL,
    filament_mm REAL,
    move_count INTEGER NOT NULL DEFAULT 0,
    extrusion_count INTEGER NOT NULL DEFAULT 0,
    travel_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (asset_id, layer_index)
);

CREATE INDEX IF NOT EXISTS idx_slice_artifacts_job
ON slice_artifacts(slice_job_id, created_at);

CREATE INDEX IF NOT EXISTS idx_gcode_layers_asset
ON gcode_layers(asset_id, layer_index);