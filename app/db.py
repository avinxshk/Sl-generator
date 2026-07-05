"""SQLite schema and connection helpers."""
import json
import os
import sqlite3

DB_PATH = os.environ.get("SL_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "sl.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    size INTEGER NOT NULL,
    traits_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    segment_id INTEGER NOT NULL REFERENCES segments(id),
    products_json TEXT NOT NULL DEFAULT '[]',
    opens_90d INTEGER NOT NULL DEFAULT 0,
    clicks_90d INTEGER NOT NULL DEFAULT 0,
    last_open_days INTEGER
);
CREATE TABLE IF NOT EXISTS historical_campaigns (
    id INTEGER PRIMARY KEY,
    subject_line TEXT NOT NULL,
    intent TEXT NOT NULL,
    tone TEXT NOT NULL,
    audience_size INTEGER NOT NULL,
    open_rate REAL NOT NULL,
    segment_id INTEGER REFERENCES segments(id),
    sent_at TEXT,
    source TEXT NOT NULL DEFAULT 'seed'
);
CREATE TABLE IF NOT EXISTS brand_voice (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    guidelines TEXT NOT NULL,
    banned_terms_json TEXT NOT NULL DEFAULT '[]',
    exemplars_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    intent TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaign_segments (
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    segment_id INTEGER NOT NULL REFERENCES segments(id),
    PRIMARY KEY (campaign_id, segment_id)
);
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    segment_id INTEGER NOT NULL REFERENCES segments(id),
    text TEXT NOT NULL,
    tone TEXT NOT NULL,
    rationale TEXT NOT NULL,
    score REAL NOT NULL,
    score_breakdown_json TEXT NOT NULL DEFAULT '{}',
    badges_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'proposed',
    edited_text TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    segment_id INTEGER NOT NULL REFERENCES segments(id),
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    open_rate REAL NOT NULL,
    sent_at TEXT,
    variant TEXT
);
"""


def get_conn(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    conn = get_conn(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in list(d):
        if key.endswith("_json"):
            d[key[: -len("_json")]] = json.loads(d.pop(key))
    return d
