"""Typed access over `engine_settings(engine_id, key)`. Each engine owns its rows."""

from __future__ import annotations

import json
import sqlite3


class EngineSettingsStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, engine_id: str, key: str, default: object = None) -> object:
        cur = self._conn.execute(
            "SELECT value FROM engine_settings WHERE engine_id=? AND key=?;",
            (engine_id, key),
        )
        row = cur.fetchone()
        if row is None:
            return default
        return json.loads(str(row["value"]))

    def set(self, engine_id: str, key: str, value: object) -> None:
        self._conn.execute(
            "INSERT INTO engine_settings(engine_id, key, value) VALUES(?, ?, ?) "
            "ON CONFLICT(engine_id, key) DO UPDATE SET value=excluded.value;",
            (engine_id, key, json.dumps(value)),
        )
        self._conn.commit()

    def seed_defaults(self, engine_id: str, defaults: dict[str, object]) -> None:
        for key, value in defaults.items():
            cur = self._conn.execute(
                "SELECT 1 FROM engine_settings WHERE engine_id=? AND key=?;",
                (engine_id, key),
            )
            if cur.fetchone() is None:
                self.set(engine_id, key, value)
