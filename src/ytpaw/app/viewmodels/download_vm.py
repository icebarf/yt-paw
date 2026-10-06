"""Download VM: URL + format → engine routing → enqueue. No Qt widgets."""

from __future__ import annotations

import sqlite3

from ytpaw.engines.registry import pick_engine
from ytpaw.infra.detail_store import detail_store_for
from ytpaw.infra.queue_store import QueueStore


def enqueue_job(
    conn: sqlite3.Connection,
    url: str,
    format_id: str = "best",
    format_label: str = "Best",
    subtitles_langs: list[str] | None = None,
    subtitles_action: str = "none",
) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Paste an http(s) URL first.")
    engine_id = pick_engine(url)
    job_id = QueueStore(conn).enqueue_single(url, engine_id)
    detail = detail_store_for(conn, engine_id)
    if detail is not None:
        detail.create(
            job_id, format_id, format_label, subtitles_langs, subtitles_action
        )
    return job_id


def enqueue_best(conn: sqlite3.Connection, url: str) -> str:
    return enqueue_job(conn, url)
