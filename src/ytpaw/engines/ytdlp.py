"""YtDlpEngine: wraps any yt-dlp-family binary via CLI.

Phase 1 scope: single-URL Best download + info parse. Playlist expansion
arrives in Phase 3. All parsing is pure (testable without network/Qt).
"""

from __future__ import annotations

import json
import re
import subprocess

from ytpaw.domain.engines_base import (
    Capability,
    DownloadOptions,
    FormatOption,
    MediaInfo,
    PlaylistEntry,
    ProgressUpdate,
)

ENGINE_ID = "ytdlp"

# --- Engine interface surface (domain.engines_base.Engine) ---
engine_id = ENGINE_ID
display_name = "yt-dlp"
binary_name = "yt-dlp"
update_repo = "yt-dlp/yt-dlp"
capabilities = Capability.SINGLE_URL | Capability.FORMAT_PICKER | Capability.PLAYLIST

# Offline fallback formats for the UI when fetch_info fails (arch §7.3).
default_formats: list[tuple[str, str]] = [
    ("Best (auto)", "best"),
    ("1080p max", "bv*[height<=1080]+ba/b[height<=1080]"),
    ("720p max", "bv*[height<=720]+ba/b[height<=720]"),
    ("Audio only", "ba/b"),
]

settings_defaults: dict[str, object] = {
    "enabled": True,
    "binary_path": "",
    "auto_update": True,
    "update_channel": "stable",
    "max_concurrent": 2,
    "info_args": "-J --no-warnings",
    "download_args": "--newline --no-colors",
}

_PROGRESS_RE = re.compile(
    r"YTPAW:\s*(?P<percent>[\d.]+)%\s*:"
    r"\s*(?P<downloaded>\d*|NA)?/(?P<total>\d*|NA)?"
    r"(:(?P<speed>[^:]*))?(:(?P<eta>.*))?"
)


def can_handle(url: str) -> float:
    u = url.strip().lower()
    if not u.startswith(("http://", "https://")):
        return 0.0
    # Generic engine: claims common video hosts weakly, everything else minimally.
    # Dedicated engines (Phase 5+) outbid with higher scores.
    if any(h in u for h in ("youtube.com", "youtu.be", "vimeo.com", "dailymotion.com")):
        return 0.6
    return 0.2


def is_playlist_url(url: str) -> bool:
    low = url.lower()
    return "list=" in low or "/playlist" in low or "/sets/" in low


def build_info_args(
    binary: str, url: str, playlist: bool = False, cookies_file: str | None = None
) -> list[str]:
    args = [binary, "-J", "--no-warnings"]
    if playlist:
        args.append("--flat-playlist")  # lazy entries: fast, id/title/url only
    else:
        args.append("--no-playlist")
    if cookies_file:
        args += ["--cookies", cookies_file]
    return [*args, url]


def parse_info_json(raw: str, url: str) -> MediaInfo:
    data: dict[str, object] = json.loads(raw)
    if data.get("_type") == "playlist":
        return _parse_playlist_json(data, url)
    title = str(data.get("title") or "Untitled")
    uploader = data.get("uploader") or data.get("channel")
    duration = data.get("duration")
    formats: list[FormatOption] = []
    raw_formats = data.get("formats")
    if isinstance(raw_formats, list):
        for f in raw_formats:
            if not isinstance(f, dict):
                continue
            fid = str(f.get("format_id") or "")
            if not fid:
                continue
            height = f.get("height")
            formats.append(
                FormatOption(
                    format_id=fid,
                    label=f"{height or '?'}p · {f.get('ext', '?')}",
                    height=int(height) if isinstance(height, int) else None,
                    ext=str(f.get("ext") or ""),
                    filesize_approx=None,
                    is_audio_only=f.get("vcodec") in (None, "none"),
                )
            )
    # Always offer Best pseudo-format first.
    formats.insert(
        0,
        FormatOption(
            format_id="best", label="Best", height=None, ext="", filesize_approx=None,
            is_audio_only=False,
        ),
    )
    thumb = data.get("thumbnail")
    langs: set[str] = set()
    for key in ("subtitles", "automatic_captions"):
        value = data.get(key)
        if isinstance(value, dict):
            langs.update(str(k) for k in value)
    return MediaInfo(
        engine_id=ENGINE_ID,
        url=url,
        title=title,
        uploader=str(uploader) if uploader else None,
        duration_s=int(duration) if isinstance(duration, int) else None,
        is_playlist=False,
        playlist_count=None,
        formats=formats,
        thumbnail_url=str(thumb) if thumb else None,
        subtitle_langs=sorted(langs)[:60] or None,
    )


def _parse_playlist_json(data: dict[str, object], url: str) -> MediaInfo:
    entries: list[PlaylistEntry] = []
    raw_entries = data.get("entries")
    if isinstance(raw_entries, list):
        for i, entry in enumerate(raw_entries, start=1):
            if not isinstance(entry, dict):
                continue
            entry_url = entry.get("url") or entry.get("webpage_url") or entry.get("id")
            if not entry_url:
                continue
            entries.append(
                PlaylistEntry(
                    index=i,
                    title=str(entry.get("title") or f"#{i}"),
                    url=str(entry_url),
                )
            )
    thumb = data.get("thumbnail")
    return MediaInfo(
        engine_id=ENGINE_ID,
        url=url,
        title=str(data.get("title") or "Playlist"),
        uploader=str(data.get("uploader") or data.get("channel") or "") or None,
        duration_s=None,
        is_playlist=True,
        playlist_count=len(entries),
        formats=[],
        thumbnail_url=str(thumb) if thumb else None,
        entries=entries,
    )


def build_download_args(
    binary: str,
    url: str,
    output_template: str,
    options: DownloadOptions | None = None,
    cookies_file: str | None = None,
) -> list[str]:
    # "Best" = yt-dlp default (bv*+ba/b auto-merge). Passing `-f best` forces a
    # pre-merged file that often doesn't exist -> "Requested format is not
    # available". So omit -f entirely for Best; explicit ids still pass -f.
    opts = options or DownloadOptions()
    args = [
        binary,
        "--newline",
        "--no-colors",
        "--no-playlist",
    ]
    if cookies_file:
        args += ["--cookies", cookies_file]
    if opts.subtitles_langs and opts.subtitles_action in ("embed", "sidecar"):
        args += ["--write-subs", "--sub-langs", ",".join(opts.subtitles_langs)]
        if opts.subtitles_action == "embed":
            args += ["--embed-subs"]
    args += [
        "-o", output_template,
        "--progress-template",
        "YTPAW:%(progress._percent_str)s:%(progress.downloaded_bytes)d/%(progress.total_bytes,progress.total_bytes_estimate)d:%(progress._speed_str)s:%(progress._eta_str)s",
    ]
    if opts.format_selector not in ("", "best", "b"):
        args += ["-f", opts.format_selector]
    return [*args, url]


def parse_progress_line(job_id: str, line: str) -> ProgressUpdate | None:
    m = _PROGRESS_RE.search(line.strip())
    if not m:
        return None
    try:
        percent = float(m.group("percent"))
    except (TypeError, ValueError):
        return None
    dl = m.group("downloaded")
    total = m.group("total")
    return ProgressUpdate(
        job_id=job_id,
        percent=percent,
        downloaded_bytes=int(dl) if dl and dl.isdigit() else None,
        total_bytes=int(total) if total and total.isdigit() else None,
        speed=m.group("speed") or None,
        eta=m.group("eta") or None,
    )


def probe_version(binary: str) -> str:
    try:
        out = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if out.returncode != 0:
        return "unknown"
    return out.stdout.strip().splitlines()[0] if out.stdout.strip() else "unknown"
