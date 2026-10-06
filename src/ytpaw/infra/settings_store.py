"""Typed access over SQLite `settings` (app.* only)."""

from __future__ import annotations

import json
import sqlite3


class SettingsStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str, default: object = None) -> object:
        cur = self._conn.execute("SELECT value FROM settings WHERE key=?;", (key,))
        row = cur.fetchone()
        if row is None:
            return default
        return json.loads(str(row["value"]))

    def set(self, key: str, value: object) -> None:
        self._conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
            (key, json.dumps(value)),
        )
        self._conn.commit()

    def seed_defaults(self, defaults: dict[str, object]) -> None:
        for key, value in defaults.items():
            cur = self._conn.execute("SELECT 1 FROM settings WHERE key=?;", (key,))
            if cur.fetchone() is None:
                self.set(key, value)
