"""Generic Engine protocol. Engines never import Qt widgets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, auto
from typing import Protocol


class Capability(Flag):
    SINGLE_URL = auto()
    PLAYLIST = auto()
    FORMAT_PICKER = auto()
    AUDIO_EXTRACT = auto()
    SUBTITLES = auto()
    AUTH_COOKIES = auto()
    SELF_UPDATE = auto()


@dataclass(frozen=True)
class FormatOption:
    format_id: str
    label: str
    height: int | None
    ext: str
    filesize_approx: int | None
    is_audio_only: bool


@dataclass(frozen=True)
class PlaylistEntry:
    index: int  # 1-based
    title: str
    url: str


@dataclass(frozen=True)
class DownloadOptions:
    """Per-job download choices (engine-interpreted selectors, opaque to UI)."""

    format_selector: str = "best"
    subtitles_langs: tuple[str, ...] = ()
    subtitles_action: str = "none"  # none|embed|sidecar


@dataclass(frozen=True)
class MediaInfo:
    engine_id: str
    url: str
    title: str
    uploader: str | None
    duration_s: int | None
    is_playlist: bool
    playlist_count: int | None
    formats: list[FormatOption]
    thumbnail_url: str | None = None
    entries: list[PlaylistEntry] | None = None
    subtitle_langs: list[str] | None = None


@dataclass(frozen=True)
class ProgressUpdate:
    job_id: str
    percent: float
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: str | None = None
    eta: str | None = None


class Engine(Protocol):
    """CLI-engine contract. Consumers (scheduler, fetcher, setup, views) must
    only use this interface — never a concrete engine module directly."""

    engine_id: str
    display_name: str
    binary_name: str  # e.g. "yt-dlp" (bundled bin/ + PATH lookup)
    update_repo: str  # GitHub "owner/repo" for stable-channel updates
    capabilities: Capability
    settings_defaults: dict[str, object]
    default_formats: list[tuple[str, str]]  # (label, selector) UI fallback

    def can_handle(self, url: str) -> float: ...
    def is_playlist_url(self, url: str) -> bool: ...
    def build_info_args(
        self, binary: str, url: str, playlist: bool, cookies_file: str | None = None
    ) -> list[str]: ...
    def parse_info_json(self, raw: str, url: str) -> MediaInfo: ...
    def build_download_args(
        self,
        binary: str,
        url: str,
        output_template: str,
        options: DownloadOptions,
        cookies_file: str | None = None,
    ) -> list[str]: ...
    def parse_progress_line(self, job_id: str, line: str) -> ProgressUpdate | None: ...
    def probe_version(self, binary: str) -> str: ...
