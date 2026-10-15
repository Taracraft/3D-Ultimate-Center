CREATE TABLE IF NOT EXISTS plate_geometry (
    plate_id TEXT PRIMARY KEY REFERENCES plates(id) ON DELETE CASCADE,
    width REAL NOT NULL CHECK (width > 0),
    depth REAL NOT NULL CHECK (depth > 0)
);

CREATE TABLE IF NOT EXISTS object_geometry (
    object_id TEXT PRIMARY KEY REFERENCES scene_objects(id) ON DELETE CASCADE,
    min_x REAL NOT NULL,
    min_y REAL NOT NULL,
    min_z REAL NOT NULL,
    max_x REAL NOT NULL,
    max_y REAL NOT NULL,
    max_z REAL NOT NULL,
    CHECK (max_x >= min_x),
    CHECK (max_y >= min_y),
    CHECK (max_z >= min_z)
);
