"""ENGINE SPECIFIC WIDGET page: info-driven format picker + thumbnail + actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ytpaw.ui.assets import icon

if TYPE_CHECKING:
    from ytpaw.domain.engines_base import MediaInfo

DEFAULT_FALLBACK: list[tuple[str, str]] = [("Best (auto)", "best")]

SUBTITLE_ACTIONS: list[tuple[str, str]] = [
    ("Off", "none"),
    ("Embed in video", "embed"),
    ("Download as files", "sidecar"),
]


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return ""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class DownloadView(QWidget):
    download = Signal(str, str, str, object, str)  # url, selector, label, langs, action
    open_jobs = Signal()
    open_settings = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._url = ""
        self._fallback_formats: list[tuple[str, str]] = list(DEFAULT_FALLBACK)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Download", self)
        title.setObjectName("pageTitle")
        self.url_echo = QLabel("", self)
        self.url_echo.setObjectName("urlEcho")
        self.url_echo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        head.addWidget(title)
        head.addSpacing(10)
        head.addWidget(self.url_echo, 1)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(14)

        card = QFrame(self)
        card.setObjectName("card")
        card_col = QVBoxLayout(card)
        card_col.setContentsMargins(16, 14, 16, 14)
        card_col.setSpacing(8)

        self.media_label = QLabel("Paste a URL on Home to begin.", card)
        self.media_label.setObjectName("cardTitle")
        self.media_label.setWordWrap(True)
        self.media_meta = QLabel("", card)
        self.media_meta.setObjectName("muted")
        self.media_meta.setWordWrap(True)
        card_col.addWidget(self.media_label)
        card_col.addWidget(self.media_meta)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format", card))
        self.format_combo = QComboBox(card)
        self._populate_fallback()
        fmt_row.addWidget(self.format_combo, 1)
        card_col.addLayout(fmt_row)

        sub_row = QHBoxLayout()
        sub_row.addWidget(QLabel("Subtitles", card))
        self.subtitles_combo = QComboBox(card)
        for label, value in SUBTITLE_ACTIONS:
            self.subtitles_combo.addItem(label, value)
        sub_row.addWidget(self.subtitles_combo)
        self.subtitles_langs = QLineEdit(card)
        self.subtitles_langs.setPlaceholderText("langs, e.g. en,de")
        sub_row.addWidget(self.subtitles_langs, 1)
        card_col.addLayout(sub_row)

        self.hint = QLabel(
            "Merging needs ffmpeg. Subtitles arrive in a later pass.", card
        )
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        card_col.addWidget(self.hint)
        card_col.addStretch(1)

        self.thumb = QLabel("thumbnail", self)
        self.thumb.setObjectName("thumbPlaceholder")
        self.thumb.setFixedSize(240, 135)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body.addWidget(card, 3)
        body.addWidget(self.thumb, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(body)

        actions = QHBoxLayout()
        self.best_btn = QPushButton("Best", self)
        self.best_btn.clicked.connect(lambda: self.format_combo.setCurrentIndex(0))
        self.download_btn = QPushButton("Download", self)
        self.download_btn.setObjectName("primaryButton")
        self.download_btn.clicked.connect(self._emit_download)
        actions.addWidget(self.best_btn)
        actions.addStretch(1)
        actions.addWidget(self.download_btn)
        root.addLayout(actions)

        root.addStretch(1)

        nav = QHBoxLayout()
        self.jobs_btn = QPushButton("Jobs", self)
        self.jobs_btn.clicked.connect(self.open_jobs.emit)
        self.settings_btn = QPushButton("Settings", self)
        self.settings_btn.clicked.connect(self.open_settings.emit)
        nav.addWidget(self.jobs_btn)
        nav.addStretch(1)
        nav.addWidget(self.settings_btn)
        root.addLayout(nav)

    def apply_icons(self) -> None:
        self.best_btn.setIcon(icon("circle-check"))
        self.download_btn.setIcon(icon("download", "#ffffff"))
        self.jobs_btn.setIcon(icon("clock-9"))
        self.settings_btn.setIcon(icon("settings"))
        for button in (
            self.best_btn,
            self.download_btn,
            self.jobs_btn,
            self.settings_btn,
        ):
            button.setIconSize(QSize(16, 16))

    # ---------- state ----------

    def set_fallback_formats(self, formats: list[tuple[str, str]]) -> None:
        """Engine-provided offline format list (label, selector)."""
        if formats:
            self._fallback_formats = list(formats)

    def set_url(self, url: str) -> None:
        self._url = url
        display = url if len(url) <= 90 else url[:87] + "…"
        self.url_echo.setText(display)

    def begin_loading(self, url: str) -> None:
        self.set_url(url)
        self.media_label.setText("Fetching info…")
        self.media_meta.setText("")
        self.hint.setText("Asking the engine about available formats.")
        self._clear_thumb("loading")

    def apply_info(self, info: MediaInfo) -> None:
        self.media_label.setText(info.title or "Untitled")
        meta_bits = [b for b in (info.uploader, _fmt_duration(info.duration_s)) if b]
        if info.is_playlist and info.playlist_count:
            meta_bits.append(f"Playlist · {info.playlist_count} videos")
        self.media_meta.setText("  ·  ".join(meta_bits))
        self._populate_formats(info)
        langs = info.subtitle_langs or []
        if langs:
            preferred = "en" if "en" in langs else langs[0]
            if not self.subtitles_langs.text().strip():
                self.subtitles_langs.setText(preferred)
            preview = ", ".join(langs[:8])
            self.subtitles_langs.setToolTip(f"available: {preview}")
            self.subtitles_langs.setPlaceholderText(f"e.g. {preview}")
        self.hint.setText("Formats from the engine. Merging needs ffmpeg.")
        if info.is_playlist:
            self.hint.setText(
                "This is a playlist — per-video queueing arrives in Phase 3. "
                "Download will take the current video only."
            )

    def apply_failure(self, message: str) -> None:
        self.media_label.setText("Could not read media info")
        self.media_meta.setText(message[:300])
        self._populate_fallback()
        self.hint.setText("You can still try Best — engines often download when listing fails.")

    def set_thumbnail(self, data: bytes) -> None:
        pix = QPixmap()
        if pix.loadFromData(data) and not pix.isNull():
            scaled = pix.scaled(
                self.thumb.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = max(0, (scaled.width() - self.thumb.width()) // 2)
            y = max(0, (scaled.height() - self.thumb.height()) // 2)
            self.thumb.setPixmap(scaled.copy(x, y, self.thumb.width(), self.thumb.height()))
            self.thumb.setText("")

    # ---------- internals ----------

    def _clear_thumb(self, text: str) -> None:
        self.thumb.setPixmap(QPixmap())
        self.thumb.setText(text)

    def _populate_fallback(self) -> None:
        self.format_combo.clear()
        for label, selector in self._fallback_formats:
            self.format_combo.addItem(label, selector)
        self.format_combo.setCurrentIndex(0)

    def _populate_formats(self, info: MediaInfo) -> None:
        combo = self.format_combo
        combo.clear()
        combo.addItem("Best (auto)", "best")
        heights = sorted(
            {f.height for f in info.formats if f.height and not f.is_audio_only},
            reverse=True,
        )
        for h in heights:
            combo.addItem(f"{h}p", f"bv*[height<={h}]+ba/b[height<={h}]")
        if any(f.is_audio_only for f in info.formats):
            combo.addItem("Audio only", "ba/b")
        combo.setCurrentIndex(0)

    def _emit_download(self) -> None:
        if not self._url:
            return
        label = self.format_combo.currentText()
        selector = str(self.format_combo.currentData() or "best")
        action = str(self.subtitles_combo.currentData() or "none")
        langs = [
            part.strip()
            for part in self.subtitles_langs.text().split(",")
            if part.strip()
        ]
        if action != "none" and not langs:
            langs = ["en"]
        self.download.emit(self._url, selector, label, langs, action)
