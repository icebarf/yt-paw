"""Per-engine job detail stores. Maps engine_id → storage adapter.

Engines never import infra; the mapping lives here so new engines add one
line here without touching UI or scheduler code.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from ytpaw.domain.engines_base import DownloadOptions
from ytpaw.infra.job_ytdlp_store import JobYtdlpStore


class JobDetailStore(Protocol):
    def create(
        self,
        job_id: str,
        format_id: str = "best",
        format_label: str = "Best",
        subtitles_langs: list[str] | None = None,
        subtitles_action: str = "none",
    ) -> None: ...
    def job_options(self, job_id: str) -> DownloadOptions: ...


def detail_store_for(conn: sqlite3.Connection, engine_id: str) -> JobDetailStore | None:
    if engine_id == "ytdlp":
        return JobYtdlpStore(conn)
    return None
