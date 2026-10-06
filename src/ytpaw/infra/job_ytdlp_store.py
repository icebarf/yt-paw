"""Per-engine detail rows for ytdlp (formats, subtitles, ...)."""

from __future__ import annotations

import json
import sqlite3

from ytpaw.domain.engines_base import DownloadOptions


class JobYtdlpStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        job_id: str,
        format_id: str = "best",
        format_label: str = "Best",
        subtitles_langs: list[str] | None = None,
        subtitles_action: str = "none",
    ) -> None:
        self._conn.execute(
            "INSERT INTO job_ytdlp(job_id, format_id, format_label, subtitles_langs,"
            " subtitles_action) VALUES(?, ?, ?, ?, ?);",
            (
                job_id,
                format_id,
                format_label,
                json.dumps(subtitles_langs or []),
                subtitles_action,
            ),
        )
        self._conn.commit()

    def get(self, job_id: str) -> sqlite3.Row | None:
        cur = self._conn.execute("SELECT * FROM job_ytdlp WHERE job_id=?;", (job_id,))
        row: sqlite3.Row | None = cur.fetchone()
        return row

    def job_options(self, job_id: str) -> DownloadOptions:
        row = self.get(job_id)
        if row is None:
            return DownloadOptions()
        try:
            raw_langs = json.loads(str(row["subtitles_langs"]))
            langs = tuple(str(x) for x in raw_langs) if isinstance(raw_langs, list) else ()
        except ValueError:
            langs = ()
        return DownloadOptions(
            format_selector=str(row["format_id"] or "best"),
            subtitles_langs=langs,
            subtitles_action=str(row["subtitles_action"] or "none"),
        )
