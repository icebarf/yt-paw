"""Canonical app settings keys + defaults (app.* only).

Per-engine defaults live on each engine (`engines/<id>.py: SETTINGS_DEFAULTS`)
and are seeded into `engine_settings` by SetupService.
"""

from __future__ import annotations

APP_DEFAULTS: dict[str, object] = {
    "app.output_dir": "~/Downloads/yt-paw",
    "app.output_template": "%(uploader)s/%(title)s [%(id)s].%(ext)s",
    "app.theme": "auto",  # auto|light|dark
    "app.concurrent": 2,
    "app.queue_mode": "auto",  # auto|sequential
    "app.auto_download_deps": True,  # fetch deno/ffmpeg when missing
}
