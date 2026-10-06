"""Phase 3 contract tests: playlist parsing + queue semantics. No network/Qt."""

from __future__ import annotations

import json
from pathlib import Path

from ytpaw.engines import ytdlp
from ytpaw.infra.db import connect, migrate
from ytpaw.infra.queue_store import QueueStore


def _db(tmp_path: Path):  # type: ignore[no-untyped-def]
    conn = connect(tmp_path / "app.db")
    migrate(conn)
    return conn


def test_is_playlist_url() -> None:
    assert ytdlp.is_playlist_url("https://www.youtube.com/playlist?list=PL123")
    assert ytdlp.is_playlist_url("https://www.youtube.com/watch?v=abc&list=PL123")
    assert not ytdlp.is_playlist_url("https://www.youtube.com/watch?v=abc")


def test_parse_playlist_json() -> None:
    raw = json.dumps(
        {
            "_type": "playlist",
            "title": "Mix",
            "entries": [
                {"id": "a", "title": "One", "url": "https://youtu.be/a"},
                {"id": "b", "title": "Two"},
                "not-a-dict",
                {"title": "no url"},
            ],
        }
    )
    info = ytdlp.parse_info_json(raw, "https://yt/playlist?list=X")
    assert info.is_playlist
    assert info.playlist_count == 2
    assert info.entries is not None
    assert info.entries[0].index == 1
    assert info.entries[0].url == "https://youtu.be/a"
    assert info.entries[1].url == "b"  # falls back to id


def test_playlist_enqueue_and_parent_lock(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        q = QueueStore(conn)
        parent = q.enqueue_playlist("https://yt/playlist?list=X", "ytdlp", "Mix", 2)
        first = q.enqueue_entry(parent, 1, "https://youtu.be/a", "ytdlp", "One")
        second = q.enqueue_entry(parent, 2, "https://youtu.be/b", "ytdlp", "Two")

        # Parent rows are containers: never scheduled.
        row = q.next_queued()
        assert row is not None and str(row["id"]) == first

        # Per-parent lock: while a child of this parent runs, siblings wait.
        q.set_status(first, "running")
        assert q.next_queued(exclude_parents={parent}) is None

        q.set_status(first, "done")
        row2 = q.next_queued()
        assert row2 is not None and str(row2["id"]) == second
    finally:
        conn.close()


def test_parent_status_and_retry_failed(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        q = QueueStore(conn)
        parent = q.enqueue_playlist("https://yt/playlist?list=X", "ytdlp", "Mix", 2)
        first = q.enqueue_entry(parent, 1, "https://youtu.be/a", "ytdlp", "One")
        second = q.enqueue_entry(parent, 2, "https://youtu.be/b", "ytdlp", "Two")

        q.refresh_parent_status(parent)
        parent_row = conn.execute("SELECT * FROM jobs WHERE id=?;", (parent,)).fetchone()
        assert parent_row["status"] == "queued"

        q.set_status(first, "running")
        q.refresh_parent_status(parent)
        parent_row = conn.execute("SELECT * FROM jobs WHERE id=?;", (parent,)).fetchone()
        assert parent_row["status"] == "running"

        q.set_status(first, "done")
        q.set_status(second, "failed", "boom")
        q.refresh_parent_status(parent)
        parent_row = conn.execute("SELECT * FROM jobs WHERE id=?;", (parent,)).fetchone()
        assert parent_row["status"] == "failed"
        assert abs(float(parent_row["progress"]) - 50.0) < 0.01

        assert q.retry_failed_children(parent) == 1
        parent_row = conn.execute("SELECT * FROM jobs WHERE id=?;", (parent,)).fetchone()
        assert parent_row["status"] == "running"  # one done + one queued

        q.set_status(second, "done")
        q.refresh_parent_status(parent)
        parent_row = conn.execute("SELECT * FROM jobs WHERE id=?;", (parent,)).fetchone()
        assert parent_row["status"] == "done"
        assert abs(float(parent_row["progress"]) - 100.0) < 0.01
    finally:
        conn.close()
