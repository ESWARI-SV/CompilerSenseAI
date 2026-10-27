-- storage/schema.sql
-- SQLite schema for optional analysis history

CREATE TABLE IF NOT EXISTS analyses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    source      TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    error_count INTEGER NOT NULL DEFAULT 0,
    stages      TEXT    NOT NULL DEFAULT ''   -- comma-separated
);

CREATE TABLE IF NOT EXISTS diagnostics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    code        TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    severity    TEXT    NOT NULL,
    line        INTEGER,
    col         INTEGER
);

CREATE TABLE IF NOT EXISTS repair_candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id         INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    candidate_id        TEXT    NOT NULL,
    description         TEXT    NOT NULL,
    method              TEXT    NOT NULL,
    rank_score          REAL,
    verification_status TEXT    NOT NULL
);
