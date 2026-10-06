"""Core job + engine-agnostic types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DownloadJob:
    id: str
    url: str
    engine_id: str
    job_type: str  # single|playlist|entry
    parent_job_id: str | None
    position: int | None
    status: str
    format_id: str | None = None
