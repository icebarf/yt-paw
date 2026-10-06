"""SQLite bootstrap + migrations. Single file `app.db`.

Tables: jobs (core) + job_ytdlp (per-engine) + settings (app.*)
+ engine_settings(engine_id, key). Versioned via PRAGMA user_version.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  finished_at TEXT,
  url TEXT NOT NULL,
  resolved_url TEXT,
  idempotency_key TEXT UNIQUE,
  engine_id TEXT NOT NULL,
  engine_version TEXT,
  engine_origin TEXT NOT NULL DEFAULT 'bundled',
  job_type TEXT NOT NULL DEFAULT 'single',
  parent_job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
  position INTEGER,
  playlist_id TEXT,
  playlist_title TEXT,
  playlist_count INTEGER,
  playlist_range TEXT,
  title TEXT,
  uploader TEXT,
  duration_s INTEGER,
  thumbnail_url TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  attempt INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  progress REAL NOT NULL DEFAULT 0,
  downloaded_bytes INTEGER,
  total_bytes INTEGER,
  output_path TEXT,
  log_path TEXT,
  error_code TEXT,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_parent ON jobs(parent_job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_engine ON jobs(engine_id);

CREATE TABLE IF NOT EXISTS job_ytdlp(
  job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  format_id TEXT NOT NULL,
  format_label TEXT,
  format_snapshot TEXT NOT NULL DEFAULT '{}',
  video_format_id TEXT,
  audio_format_id TEXT,
  merge_output_format TEXT,
  audio_extract INTEGER NOT NULL DEFAULT 0,
  audio_codec TEXT,
  subtitles_langs TEXT NOT NULL DEFAULT '[]',
  subtitles_action TEXT NOT NULL DEFAULT 'none',
  playlist_start INTEGER,
  playlist_end INTEGER,
  cookies_used INTEGER NOT NULL DEFAULT 0,
  output_template TEXT,
  extra_args TEXT NOT NULL DEFAULT '[]',
  engine_args_hash TEXT
);

CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS engine_settings(
  engine_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (engine_id, key)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    cur = conn.execute("PRAGMA user_version;")
    version = int(cur.fetchone()[0])
    if version < 1:
        conn.executescript(_SCHEMA_V1)
        conn.execute("PRAGMA user_version=1;")
        conn.commit()
        version = 1
    return version
