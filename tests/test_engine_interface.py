"""Engine interface gates: registry-driven routing with a fake engine.

Proves the core is engine-agnostic: a non-yt-dlp engine can be registered and
flow through routing/enqueue without touching core code.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ytpaw.app.viewmodels.download_vm import enqueue_job
from ytpaw.domain.engines_base import (
    Capability,
    DownloadOptions,
    MediaInfo,
    ProgressUpdate,
)
from ytpaw.engines import registry
from ytpaw.infra.db import connect, migrate
from ytpaw.infra.queue_store import QueueStore


class FakeEngine:
    def __init__(self) -> None:
        self.engine_id = "fake"
        self.settings_defaults: dict[str, object] = {"enabled": True}
        self.default_formats: list[tuple[str, str]] = [("Best", "best")]

    display_name = "Fake Engine"
    binary_name = "fake-bin"
    update_repo = "fake/repo"
    capabilities = Capability.SINGLE_URL

    def can_handle(self, url: str) -> float:
        return 0.99 if "fake.example" in url else 0.0

    def is_playlist_url(self, url: str) -> bool:
        return False

    def build_info_args(
        self, binary: str, url: str, playlist: bool, cookies_file: str | None = None
    ) -> list[str]:
        return [binary, "-J", url]

    def parse_info_json(self, raw: str, url: str) -> MediaInfo:
        return MediaInfo("fake", url, "Fake", None, None, False, None, [])

    def build_download_args(
        self,
        binary: str,
        url: str,
        output_template: str,
        options: DownloadOptions,
        cookies_file: str | None = None,
    ) -> list[str]:
        return [binary, url, "-o", output_template, "-f", options.format_selector]

    def parse_progress_line(self, job_id: str, line: str) -> ProgressUpdate | None:
        return None

    def probe_version(self, binary: str) -> str:
        return "1.0"


def _db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "app.db")
    migrate(conn)
    return conn


@pytest.fixture()
def fake_engine():  # type: ignore[no-untyped-def]
    registry.register(FakeEngine())
    yield
    registry.unregister("fake")


def test_registry_routes_fake_engine(fake_engine: None) -> None:
    assert registry.pick_engine("https://fake.example/v/1") == "fake"
    # Real engine still wins for its own hosts.
    assert registry.pick_engine("https://www.youtube.com/watch?v=a") == "ytdlp"


def test_fake_engine_enqueues_without_detail_store(
    tmp_path: Path, fake_engine: None
) -> None:
    conn = _db(tmp_path)
    try:
        job_id = enqueue_job(conn, "https://fake.example/v/1")
        rows = QueueStore(conn).list_recent()
        assert len(rows) == 1
        assert str(rows[0]["id"]) == job_id
        assert str(rows[0]["engine_id"]) == "fake"
        # No engine-specific detail table for the fake engine: no crash, no row.
        cur = conn.execute("SELECT COUNT(*) FROM job_ytdlp;")
        assert int(cur.fetchone()[0]) == 0
    finally:
        conn.close()
