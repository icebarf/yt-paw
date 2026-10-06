"""Phase 1 contract tests: no network. Fixtures only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ytpaw.app.viewmodels.download_vm import enqueue_best
from ytpaw.engines import ytdlp
from ytpaw.engines.registry import pick_engine
from ytpaw.infra.db import connect, migrate
from ytpaw.infra.job_ytdlp_store import JobYtdlpStore
from ytpaw.infra.queue_store import QueueStore


def _db(tmp_path: Path):  # type: ignore[no-untyped-def]
    conn = connect(tmp_path / "app.db")
    migrate(conn)
    return conn


def test_router_picks_ytdlp() -> None:
    assert pick_engine("https://www.youtube.com/watch?v=abc") == "ytdlp"
    with pytest.raises(ValueError):
        pick_engine("file:///etc/passwd")


def test_parse_info_fixture() -> None:
    raw = json.dumps(
        {
            "title": "Demo",
            "uploader": "chan",
            "duration": 61,
            "thumbnail": "https://example.com/t.jpg",
            "formats": [
                {"format_id": "18", "ext": "mp4", "height": 360, "vcodec": "h264"},
                {"format_id": "251", "ext": "webm", "height": None, "vcodec": "none"},
            ],
        }
    )
    info = ytdlp.parse_info_json(raw, "https://youtu.be/x")
    assert info.title == "Demo"
    assert info.thumbnail_url == "https://example.com/t.jpg"
    assert info.formats[0].format_id == "best"  # pseudo-format first
    assert any(f.format_id == "18" for f in info.formats)


def test_parse_progress_line() -> None:
    upd = ytdlp.parse_progress_line(
        "j1", "YTPAW: 42.1%:123/456:1.2MiB/s:00:03"
    )
    assert upd is not None and abs(upd.percent - 42.1) < 0.01
    assert upd.downloaded_bytes == 123 and upd.total_bytes == 456
    na = ytdlp.parse_progress_line("j1", "YTPAW:  2.7%:NA/NA:   1.05MiB/s:00:08")
    assert na is not None and abs(na.percent - 2.7) < 0.01
    assert ytdlp.parse_progress_line("j1", "[info] noise") is None


def test_enqueue_best_creates_job_and_detail(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        job_id = enqueue_best(conn, "https://www.youtube.com/watch?v=abc")
        rows = QueueStore(conn).list_recent()
        assert len(rows) == 1 and str(rows[0]["id"]) == job_id
        detail = JobYtdlpStore(conn).get(job_id)
        assert detail is not None and str(detail["format_id"]) == "best"
    finally:
        conn.close()


def test_retry_resets_failed_job(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        job_id = enqueue_best(conn, "https://www.youtube.com/watch?v=abc")
        q = QueueStore(conn)
        q.set_status(job_id, "failed", "boom")
        q.set_progress(job_id, 42.0)
        q.retry(job_id)
        row = q.list_recent()[0]
        assert str(row["status"]) == "queued"
        assert row["error"] is None
        assert float(row["progress"]) == 0.0
    finally:
        conn.close()


def test_build_download_args_shape() -> None:
    from ytpaw.domain.engines_base import DownloadOptions

    best = ytdlp.build_download_args(
        "yt-dlp", "https://youtu.be/x", "/tmp/%(title)s.%(ext)s", DownloadOptions()
    )
    assert best[:3] == ["yt-dlp", "--newline", "--no-colors"]
    assert "-f" not in best  # Best = yt-dlp default, no -f flag
    explicit = ytdlp.build_download_args(
        "yt-dlp", "https://youtu.be/x", "/tmp/%(title)s.%(ext)s", DownloadOptions("18")
    )
    assert "-f" in explicit and "18" in explicit
