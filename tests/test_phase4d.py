"""Phase 4d gates: subtitles parsing/args + cookies args + job options store."""

from __future__ import annotations

import json
from pathlib import Path

from ytpaw.domain.engines_base import DownloadOptions
from ytpaw.engines import ytdlp
from ytpaw.infra.db import connect, migrate
from ytpaw.infra.job_ytdlp_store import JobYtdlpStore
from ytpaw.infra.queue_store import QueueStore


def _db(tmp_path: Path):  # type: ignore[no-untyped-def]
    conn = connect(tmp_path / "app.db")
    migrate(conn)
    return conn


def test_parse_info_subtitle_langs() -> None:
    raw = json.dumps(
        {
            "title": "t",
            "formats": [],
            "subtitles": {"en": [], "de": []},
            "automatic_captions": {"en": [], "fr": []},
        }
    )
    info = ytdlp.parse_info_json(raw, "https://youtu.be/x")
    assert info.subtitle_langs == ["de", "en", "fr"]


def test_build_info_args_with_cookies() -> None:
    args = ytdlp.build_info_args("yt-dlp", "https://youtu.be/x", False, "/tmp/c.txt")
    assert "--no-playlist" in args
    assert args[args.index("--cookies") + 1] == "/tmp/c.txt"
    playlist_args = ytdlp.build_info_args(
        "yt-dlp", "https://yt/playlist?list=X", True, None
    )
    assert "--flat-playlist" in playlist_args
    assert "--cookies" not in playlist_args


def test_build_download_args_subtitles_modes() -> None:
    embed = ytdlp.build_download_args(
        "yt-dlp", "u", "t", DownloadOptions("best", ("en", "de"), "embed")
    )
    assert "--write-subs" in embed and "--embed-subs" in embed
    assert "en,de" in embed

    sidecar = ytdlp.build_download_args(
        "yt-dlp", "u", "t", DownloadOptions("best", ("en",), "sidecar")
    )
    assert "--write-subs" in sidecar
    assert "--embed-subs" not in sidecar

    off = ytdlp.build_download_args(
        "yt-dlp", "u", "t", DownloadOptions("best", ("en",), "none")
    )
    assert "--write-subs" not in off


def test_build_download_args_with_cookies() -> None:
    args = ytdlp.build_download_args(
        "yt-dlp", "u", "t", DownloadOptions(), "/tmp/cookies.txt"
    )
    assert args[args.index("--cookies") + 1] == "/tmp/cookies.txt"


def test_job_options_roundtrip(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        job_id = QueueStore(conn).enqueue_single("https://youtu.be/x")
        store = JobYtdlpStore(conn)
        store.create(job_id, "18", "720p", ["en", "de"], "embed")
        options = store.job_options(job_id)
        assert options.format_selector == "18"
        assert options.subtitles_langs == ("en", "de")
        assert options.subtitles_action == "embed"

        assert store.job_options("missing").format_selector == "best"
        assert store.job_options("missing").subtitles_langs == ()
    finally:
        conn.close()
