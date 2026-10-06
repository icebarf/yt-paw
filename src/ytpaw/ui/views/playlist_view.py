"""PLAYLIST page: flat entry list, range picker, sequential download."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ytpaw.ui.assets import icon

if TYPE_CHECKING:
    from ytpaw.domain.engines_base import MediaInfo, PlaylistEntry

DEFAULT_FALLBACK: list[tuple[str, str]] = [("Best (auto)", "best")]


class PlaylistView(QWidget):
    download = Signal(object)  # {url, title, entries:[PlaylistEntry], selector, label}
    open_jobs = Signal()
    open_settings = Signal()
    go_home = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._info: MediaInfo | None = None
        self._fallback_formats: list[tuple[str, str]] = list(DEFAULT_FALLBACK)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Playlist", self)
        title.setObjectName("pageTitle")
        self.title_label = QLabel("", self)
        self.title_label.setObjectName("cardTitle")
        self.meta_label = QLabel("", self)
        self.meta_label.setObjectName("muted")
        head.addWidget(title)
        head.addSpacing(10)
        head.addWidget(self.title_label, 1)
        head.addWidget(self.meta_label)
        root.addLayout(head)

        self.list = QListWidget(self)
        self.list.itemChanged.connect(self._update_count)
        root.addWidget(self.list, 1)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("From", self))
        self.from_spin = QSpinBox(self)
        self.from_spin.setMinimum(1)
        self.from_spin.setMaximumWidth(80)
        controls.addWidget(self.from_spin)
        controls.addWidget(QLabel("To", self))
        self.to_spin = QSpinBox(self)
        self.to_spin.setMinimum(1)
        self.to_spin.setMaximumWidth(80)
        controls.addWidget(self.to_spin)
        range_btn = QPushButton("Select range", self)
        range_btn.clicked.connect(self._select_range)
        controls.addWidget(range_btn)
        all_btn = QPushButton("All", self)
        all_btn.clicked.connect(lambda: self._set_checked(None))
        controls.addWidget(all_btn)
        none_btn = QPushButton("None", self)
        none_btn.clicked.connect(lambda: self._set_checked(set()))
        controls.addWidget(none_btn)
        self.range_btn = range_btn
        self.all_btn = all_btn
        self.none_btn = none_btn

        controls.addStretch(1)
        controls.addWidget(QLabel("Format", self))
        self.format_combo = QComboBox(self)
        for label, selector in self._fallback_formats:
            self.format_combo.addItem(label, selector)
        controls.addWidget(self.format_combo)
        root.addLayout(controls)

        actions = QHBoxLayout()
        self.download_btn = QPushButton("Download selected (0)", self)
        self.download_btn.setObjectName("primaryButton")
        self.download_btn.clicked.connect(self._emit_download)
        actions.addStretch(1)
        actions.addWidget(self.download_btn)
        root.addLayout(actions)

        nav = QHBoxLayout()
        self.home_btn = QPushButton("Home", self)
        self.home_btn.clicked.connect(self.go_home.emit)
        self.jobs_btn = QPushButton("Jobs", self)
        self.jobs_btn.clicked.connect(self.open_jobs.emit)
        self.settings_btn = QPushButton("Settings", self)
        self.settings_btn.clicked.connect(self.open_settings.emit)
        nav.addWidget(self.home_btn)
        nav.addWidget(self.jobs_btn)
        nav.addStretch(1)
        nav.addWidget(self.settings_btn)
        root.addLayout(nav)

    def apply_icons(self) -> None:
        self.range_btn.setIcon(icon("check"))
        self.all_btn.setIcon(icon("circle-check"))
        self.none_btn.setIcon(icon("octagon-minus"))
        self.download_btn.setIcon(icon("download", "#ffffff"))
        self.home_btn.setIcon(icon("paw-print"))
        self.jobs_btn.setIcon(icon("clock-9"))
        self.settings_btn.setIcon(icon("settings"))
        for button in (
            self.range_btn,
            self.all_btn,
            self.none_btn,
            self.download_btn,
            self.home_btn,
            self.jobs_btn,
            self.settings_btn,
        ):
            button.setIconSize(QSize(16, 16))

    # ---------- state ----------

    def set_fallback_formats(self, formats: list[tuple[str, str]]) -> None:
        if not formats:
            return
        self._fallback_formats = list(formats)
        self.format_combo.clear()
        for label, selector in self._fallback_formats:
            self.format_combo.addItem(label, selector)

    def apply_info(self, info: MediaInfo) -> None:
        self._info = info
        entries = info.entries or []
        self.title_label.setText(info.title)
        self.meta_label.setText(f"{len(entries)} videos · download is sequential")
        self.list.blockSignals(True)
        self.list.clear()
        for entry in entries:
            item = QListWidgetItem(f"{entry.index:03d}.  {entry.title}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, entry.index)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.from_spin.setMaximum(max(1, len(entries)))
        self.to_spin.setMaximum(max(1, len(entries)))
        self.from_spin.setValue(1)
        self.to_spin.setValue(min(len(entries), 10) if entries else 1)
        self._update_count()

    # ---------- internals ----------

    def _selected_entries(self) -> list[PlaylistEntry]:
        if self._info is None:
            return []
        by_index = {e.index: e for e in (self._info.entries or [])}
        selected = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                idx = int(item.data(Qt.ItemDataRole.UserRole))
                entry = by_index.get(idx)
                if entry is not None:
                    selected.append(entry)
        return selected

    def _set_checked(self, indexes: set[int] | None) -> None:
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            item = self.list.item(i)
            idx = int(item.data(Qt.ItemDataRole.UserRole))
            check = indexes is None or idx in indexes
            item.setCheckState(
                Qt.CheckState.Checked if check else Qt.CheckState.Unchecked
            )
        self.list.blockSignals(False)
        self._update_count()

    def _select_range(self) -> None:
        low = min(self.from_spin.value(), self.to_spin.value())
        high = max(self.from_spin.value(), self.to_spin.value())
        self._set_checked(set(range(low, high + 1)))

    def _update_count(self) -> None:
        n = len(self._selected_entries())
        self.download_btn.setText(f"Download selected ({n})")
        self.download_btn.setEnabled(n > 0)

    def _emit_download(self) -> None:
        if self._info is None:
            return
        entries = self._selected_entries()
        if not entries:
            return
        label = self.format_combo.currentText()
        selector = str(self.format_combo.currentData() or "best")
        self.download.emit(
            {
                "url": self._info.url,
                "title": self._info.title,
                "entries": entries,
                "selector": selector,
                "label": label,
            }
        )
