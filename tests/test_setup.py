"""Phase 0 gates: DB migrates, settings seed, self-setup creates dirs."""

from __future__ import annotations

from pathlib import Path

from ytpaw.domain.settings_keys import APP_DEFAULTS
from ytpaw.engines import registry
from ytpaw.infra.db import connect, migrate
from ytpaw.infra.engine_settings_store import EngineSettingsStore
from ytpaw.infra.settings_store import SettingsStore
from ytpaw.infra.setup_service import ensure_ready, resolve_engine_status


def test_migrate_and_seed(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    conn = connect(db)
    try:
        assert migrate(conn) == 1
        SettingsStore(conn).seed_defaults(APP_DEFAULTS)
        assert SettingsStore(conn).get("app.concurrent") == 2
        EngineSettingsStore(conn).seed_defaults("ytdlp", {"max_concurrent": 2})
        assert EngineSettingsStore(conn).get("ytdlp", "max_concurrent") == 2
    finally:
        conn.close()


def test_ensure_ready_creates_layout(tmp_path: Path) -> None:
    res = ensure_ready(tmp_path)
    assert res.db_path.exists()
    assert (tmp_path / "logs").exists()
    assert res.schema_version == 1
    assert res.first_run is True  # no DB before this call
    assert res.engines, "at least one engine should be registered"
    ytdlp_status = next((s for s in res.engines if s.engine_id == "ytdlp"), None)
    assert ytdlp_status is not None
    assert ytdlp_status.origin in {"bundled", "custom", "system", "missing"}
    assert isinstance(ytdlp_status.enabled, bool)

    again = ensure_ready(tmp_path)
    assert again.first_run is False  # DB now exists


def test_fresh_profile_defaults_to_auto_source(tmp_path: Path) -> None:
    res = ensure_ready(tmp_path)
    conn = connect(res.db_path)
    try:
        source = EngineSettingsStore(conn).get("ytdlp", "source")
        assert source == "auto"  # fresh installs are app-managed (friend-friendly)
    finally:
        conn.close()


def test_resolve_engine_status_reads_engine_settings(tmp_path: Path) -> None:
    res = ensure_ready(tmp_path)
    conn = connect(res.db_path)
    try:
        store = EngineSettingsStore(conn)
        store.set("ytdlp", "enabled", False)
        store.set("ytdlp", "source", "path")
        store.set("ytdlp", "binary_path", "/nonexistent/yt-dlp")
        engine = registry.get_engine("ytdlp")
        status = resolve_engine_status(engine, conn)
        assert status.origin == "custom"
        assert status.enabled is False
        assert Path(str(status.path)) == Path("/nonexistent/yt-dlp")
        assert status.version == "unknown"  # probe fails gracefully
    finally:
        conn.close()


def test_source_system_ignores_binary_path(tmp_path: Path) -> None:
    res = ensure_ready(tmp_path)
    conn = connect(res.db_path)
    try:
        store = EngineSettingsStore(conn)
        store.set("ytdlp", "source", "system")
        store.set("ytdlp", "binary_path", "/nonexistent/yt-dlp")
        engine = registry.get_engine("ytdlp")
        status = resolve_engine_status(engine, conn)
        # Resolved from PATH (or missing on machines without yt-dlp installed).
        assert status.origin in {"system", "missing"}
        assert Path(str(status.path or "x")) != Path("/nonexistent/yt-dlp")
    finally:
        conn.close()


def test_source_auto_prefers_bundled_falls_back_to_system(tmp_path: Path) -> None:
    res = ensure_ready(tmp_path)
    conn = connect(res.db_path)
    try:
        store = EngineSettingsStore(conn)
        store.set("ytdlp", "source", "auto")
        engine = registry.get_engine("ytdlp")
        status = resolve_engine_status(engine, conn)
        assert status.origin in {"bundled", "system", "missing"}
    finally:
        conn.close()


def test_legacy_binary_path_implies_path_source(tmp_path: Path) -> None:
    res = ensure_ready(tmp_path)
    conn = connect(res.db_path)
    try:
        # Simulate a pre-source-modes DB row: binary_path set, no source key.
        conn.execute(
            "DELETE FROM engine_settings WHERE engine_id='ytdlp' AND key='source';"
        )
        conn.commit()
        EngineSettingsStore(conn).set("ytdlp", "binary_path", "/legacy/yt-dlp")
        engine = registry.get_engine("ytdlp")
        status = resolve_engine_status(engine, conn)
        assert status.origin == "custom"
        assert Path(str(status.path)) == Path("/legacy/yt-dlp")
    finally:
        conn.close()
