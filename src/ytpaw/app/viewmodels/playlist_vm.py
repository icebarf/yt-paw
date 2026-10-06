"""Playlist VM: selected entries → parent + child jobs. No Qt widgets."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from ytpaw.infra.detail_store import detail_store_for
from ytpaw.infra.queue_store import QueueStore

if TYPE_CHECKING:
    from ytpaw.domain.engines_base import PlaylistEntry


def enqueue_playlist(
    conn: sqlite3.Connection,
    url: str,
    title: str,
    entries: list[PlaylistEntry],
    engine_id: str = "ytdlp",
    format_id: str = "best",
    format_label: str = "Best",
) -> str:
    if not entries:
        raise ValueError("Select at least one video.")
    store = QueueStore(conn)
    parent_id = store.enqueue_playlist(url, engine_id, title, len(entries))
    detail = detail_store_for(conn, engine_id)
    for entry in entries:
        child_id = store.enqueue_entry(
            parent_id, entry.index, entry.url, engine_id, entry.title
        )
        if detail is not None:
            detail.create(child_id, format_id, format_label)
    store.refresh_parent_status(parent_id)
    return parent_id
