CREATE TABLE IF NOT EXISTS mesh_metadata (
    asset_id TEXT PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    triangle_count INTEGER NOT NULL CHECK (triangle_count >= 0),
    vertex_count INTEGER NOT NULL CHECK (vertex_count >= 0),
    min_x REAL NOT NULL,
    min_y REAL NOT NULL,
    min_z REAL NOT NULL,
    max_x REAL NOT NULL,
    max_y REAL NOT NULL,
    max_z REAL NOT NULL,
    volume_mm3 REAL,
    manifold INTEGER,
    watertight INTEGER,
    candidate_faces_json TEXT NOT NULL DEFAULT '[]',
    analyzed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preview_jobs (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    preview_asset_id TEXT REFERENCES assets(id),
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_preview_jobs_status
ON preview_jobs(status, created_at);
