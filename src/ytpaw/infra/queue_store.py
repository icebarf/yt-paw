"""SQLite-backed FIFO queue over `jobs`. Phase 1: singles only, sequential default."""

from __future__ import annotations

import sqlite3
import uuid


def _new_id() -> str:
    return uuid.uuid4().hex


class QueueStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def enqueue_single(
        self, url: str, engine_id: str = "ytdlp", title: str | None = None
    ) -> str:
        job_id = _new_id()
        self._conn.execute(
            "INSERT INTO jobs(id, url, engine_id, job_type, title, status)"
            " VALUES(?, ?, ?, 'single', ?, 'queued');",
            (job_id, url, engine_id, title),
        )
        self._conn.commit()
        return job_id

    def enqueue_playlist(
        self, url: str, engine_id: str, title: str, count: int
    ) -> str:
        job_id = _new_id()
        self._conn.execute(
            "INSERT INTO jobs(id, url, engine_id, job_type, title, status, playlist_count)"
            " VALUES(?, ?, ?, 'playlist', ?, 'queued', ?);",
            (job_id, url, engine_id, title, count),
        )
        self._conn.commit()
        return job_id

    def enqueue_entry(
        self, parent_id: str, position: int, url: str, engine_id: str, title: str
    ) -> str:
        job_id = _new_id()
        self._conn.execute(
            "INSERT INTO jobs(id, url, engine_id, job_type, parent_job_id, position, title, status)"
            " VALUES(?, ?, ?, 'entry', ?, ?, ?, 'queued');",
            (job_id, url, engine_id, parent_id, position, title),
        )
        self._conn.commit()
        return job_id

    def next_queued(self, exclude_parents: set[str] | None = None) -> sqlite3.Row | None:
        """Next runnable job: singles + playlist entries only (parents are
        containers). Children whose parent is currently running are skipped
        (per-parent sequential lock, arch §5.5)."""
        sql = (
            "SELECT * FROM jobs WHERE status='queued'"
            " AND job_type IN ('single', 'entry')"
        )
        params: list[str] = []
        if exclude_parents:
            marks = ",".join("?" * len(exclude_parents))
            sql += f" AND (parent_job_id IS NULL OR parent_job_id NOT IN ({marks}))"
            params.extend(sorted(exclude_parents))
        sql += " ORDER BY created_at, COALESCE(position, 0) LIMIT 1;"
        cur = self._conn.execute(sql, params)
        row: sqlite3.Row | None = cur.fetchone()
        return row

    def refresh_parent_status(self, parent_id: str) -> None:
        rows = self._conn.execute(
            "SELECT status FROM jobs WHERE parent_job_id=?;", (parent_id,)
        ).fetchall()
        if not rows:
            return
        statuses = [str(r["status"]) for r in rows]
        total = len(statuses)
        done = statuses.count("done")
        running = statuses.count("running")
        queued = statuses.count("queued")
        failed = statuses.count("failed")
        cancelled = statuses.count("cancelled")
        if running or (queued and (done or failed or cancelled)):
            parent = "running"
        elif queued == total:
            parent = "queued"
        elif failed:
            parent = "failed"
        elif cancelled and done == 0:
            parent = "cancelled"
        else:
            parent = "done"
        progress = 100.0 * done / total
        terminal = parent in ("done", "failed", "cancelled")
        self._conn.execute(
            "UPDATE jobs SET status=?, progress=?,"
            " updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?;",
            (parent, progress, parent_id),
        )
        if terminal:
            self._conn.execute(
                "UPDATE jobs SET finished_at=COALESCE(finished_at,"
                " strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE id=?;",
                (parent_id,),
            )
        self._conn.commit()

    def retry_failed_children(self, parent_id: str) -> int:
        cur = self._conn.execute(
            "UPDATE jobs SET status='queued', progress=0, error=NULL, finished_at=NULL,"
            " updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')"
            " WHERE parent_job_id=? AND status IN ('failed', 'cancelled');",
            (parent_id,),
        )
        self._conn.commit()
        count = cur.rowcount
        if count:
            self.refresh_parent_status(parent_id)
        return count

    def set_status(
        self, job_id: str, status: str, error: str | None = None
    ) -> None:
        self._conn.execute(
            "UPDATE jobs SET status=?, error=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')"
            " WHERE id=?;",
            (status, error, job_id),
        )
        self._conn.commit()

    def set_progress(self, job_id: str, percent: float) -> None:
        self._conn.execute(
            "UPDATE jobs SET progress=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')"
            " WHERE id=?;",
            (percent, job_id),
        )
        self._conn.commit()

    def finish(self, job_id: str, output_path: str | None) -> None:
        self._conn.execute(
            "UPDATE jobs SET status='done', progress=100, output_path=?,"
            " finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?;",
            (output_path, job_id),
        )
        self._conn.commit()

    def retry(self, job_id: str) -> None:
        self._conn.execute(
            "UPDATE jobs SET status='queued', progress=0, error=NULL, finished_at=NULL,"
            " updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?;",
            (job_id,),
        )
        self._conn.commit()

    def list_recent(self, limit: int = 50) -> list[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?;", (limit,)
        )
        return list(cur.fetchall())
