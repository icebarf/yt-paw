"""SETTINGS page: output dir, theme, concurrency, engine info + per-engine config."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ytpaw.ui.assets import icon

THEME_LABELS = {"auto": "System theme", "light": "Light", "dark": "Dark"}
THEME_ICONS = {"auto": "paw-print", "light": "sun", "dark": "moon"}

SOURCE_LABELS: dict[str, str] = {
    "system": "System (PATH)",
    "path": "Custom path (override)",
    "auto": "Auto (app-managed)",
}


class _EngineBox(QGroupBox):
    """One engine: enabled, source mode, active resolved path, path override."""

    update_requested = Signal(str)  # engine_id

    def __init__(self, spec: dict[str, object], parent: QWidget | None = None) -> None:
        engine_id = str(spec.get("engine_id") or "")
        name = str(spec.get("display_name") or engine_id)
        origin = str(spec.get("origin") or "missing")
        version = spec.get("version")
        version_txt = f" · {version}" if version else ""
        super().__init__(f"{name} — {origin}{version_txt}", parent)
        self.engine_id = engine_id

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self.enabled = QCheckBox("Enabled", self)
        self.enabled.setChecked(bool(spec.get("enabled", True)))
        layout.addWidget(self.enabled)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source", self))
        self.source = QComboBox(self)
        for key, label in SOURCE_LABELS.items():
            self.source.addItem(label, key)
        current = str(spec.get("source") or "system")
        index = self.source.findData(current)
        self.source.setCurrentIndex(max(0, index))
        self.source.currentIndexChanged.connect(self._sync_rows)
        source_row.addWidget(self.source)
        source_row.addStretch(1)
        layout.addLayout(source_row)

        active_row = QHBoxLayout()
        active_row.addWidget(QLabel("Active", self))
        self.active = QLineEdit(self)
        self.active.setReadOnly(True)
        active_path = spec.get("active_path")
        self.active.setText(str(active_path) if active_path else "not found")
        if version:
            self.active.setToolTip(f"version {version}")
        active_row.addWidget(self.active, 1)
        layout.addLayout(active_row)

        self._path_widget = QWidget(self)
        path_row = QHBoxLayout(self._path_widget)
        path_row.setContentsMargins(0, 0, 0, 0)
        self.binary_path = QLineEdit(self._path_widget)
        self.binary_path.setText(str(spec.get("binary_path") or ""))
        self.binary_path.setPlaceholderText("full path to the engine binary")
        browse = QPushButton("Browse…", self._path_widget)
        browse.clicked.connect(self._browse)
        path_row.addWidget(QLabel("Binary path", self._path_widget))
        path_row.addWidget(self.binary_path, 1)
        path_row.addWidget(browse)
        layout.addWidget(self._path_widget)

        cookies_row = QHBoxLayout()
        self.cookies_file = QLineEdit(self)
        self.cookies_file.setText(str(spec.get("cookies_file") or ""))
        self.cookies_file.setPlaceholderText("optional cookies.txt for private videos")
        browse_cookies = QPushButton("Browse…", self)
        browse_cookies.clicked.connect(self._browse_cookies)
        clear_cookies = QPushButton("Clear", self)
        clear_cookies.clicked.connect(lambda: self.cookies_file.setText(""))
        cookies_row.addWidget(QLabel("Cookies", self))
        cookies_row.addWidget(self.cookies_file, 1)
        cookies_row.addWidget(browse_cookies)
        cookies_row.addWidget(clear_cookies)
        layout.addLayout(cookies_row)

        self._update_btn = QPushButton("Get latest (stable)", self)
        self._update_btn.clicked.connect(
            lambda: self.update_requested.emit(self.engine_id)
        )
        update_row = QHBoxLayout()
        update_row.addWidget(self._update_btn)
        update_row.addStretch(1)
        layout.addLayout(update_row)

        self._sync_rows()

    def apply_icons(self) -> None:
        self._update_btn.setIcon(icon("arrow-down"))
        self._update_btn.setIconSize(QSize(16, 16))

    def _sync_rows(self) -> None:
        source = self.source.currentData()
        self._path_widget.setVisible(source == "path")
        self._update_btn.setVisible(source == "auto")

    def _browse(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(self, "Select engine binary")
        if chosen:
            self.binary_path.setText(chosen)

    def _browse_cookies(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Select cookies file", filter="Cookies (*.txt);;All files (*)"
        )
        if chosen:
            self.cookies_file.setText(chosen)

    def settings(self) -> dict[str, object]:
        return {
            "engine_id": self.engine_id,
            "enabled": self.enabled.isChecked(),
            "source": str(self.source.currentData() or "system"),
            "binary_path": self.binary_path.text().strip(),
            "cookies_file": self.cookies_file.text().strip(),
        }


class SettingsView(QWidget):
    saved = Signal(str, int)  # output_dir, concurrent
    engines_saved = Signal(object)  # list[dict]
    engine_update_requested = Signal(str)  # engine_id
    theme_changed = Signal(str)  # auto|light|dark
    open_jobs = Signal()
    go_home = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._engine_boxes: list[_EngineBox] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(12)

        title = QLabel("Settings", self)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        dir_row = QHBoxLayout()
        self.output_dir = QLineEdit(self)
        browse = QPushButton("Browse…", self)
        browse.clicked.connect(self._browse)
        dir_row.addWidget(self.output_dir, 1)
        dir_row.addWidget(browse)
        form.addRow(QLabel("Download folder", self), dir_row)

        self.theme = QComboBox(self)
        self.theme.addItems(list(THEME_LABELS.values()))
        self.theme.setMaximumWidth(220)
        self.theme.currentTextChanged.connect(
            lambda label: self.theme_changed.emit(
                next(k for k, v in THEME_LABELS.items() if v == label)
            )
        )
        form.addRow(QLabel("Theme", self), self.theme)

        self.concurrent = QSpinBox(self)
        self.concurrent.setRange(1, 4)
        self.concurrent.setMaximumWidth(90)
        form.addRow(QLabel("Concurrent downloads", self), self.concurrent)
        root.addLayout(form)

        self.engine_info = QLabel("", self)
        self.engine_info.setObjectName("muted")
        self.engine_info.setWordWrap(True)
        root.addWidget(self.engine_info)

        self._engines_host = QVBoxLayout()
        self._engines_host.setSpacing(8)
        root.addLayout(self._engines_host)

        save_row = QHBoxLayout()
        self.save_btn = QPushButton("Save", self)
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save)
        save_row.addStretch(1)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)

        root.addStretch(1)

        nav = QHBoxLayout()
        home_btn = QPushButton("Home", self)
        home_btn.clicked.connect(self.go_home.emit)
        jobs_btn = QPushButton("Jobs", self)
        jobs_btn.clicked.connect(self.open_jobs.emit)
        nav.addWidget(home_btn)
        nav.addWidget(jobs_btn)
        nav.addStretch(1)
        root.addLayout(nav)

    def load(self, output_dir: str, theme_name: str, concurrent: int, engine: str) -> None:
        self.output_dir.setText(output_dir)
        self.theme.blockSignals(True)
        self.theme.setCurrentText(THEME_LABELS.get(theme_name, "System theme"))
        self.theme.blockSignals(False)
        self.concurrent.setValue(concurrent)
        self.engine_info.setText(engine)

    def load_engines(self, engines: list[dict[str, object]]) -> None:
        while self._engines_host.count():
            item = self._engines_host.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._engine_boxes.clear()
        for spec in engines:
            box = _EngineBox(spec, self)
            box.update_requested.connect(self.engine_update_requested.emit)
            box.apply_icons()
            self._engine_boxes.append(box)
            self._engines_host.addWidget(box)

    def _browse(self) -> None:
        start = self.output_dir.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Choose download folder", start)
        if chosen:
            self.output_dir.setText(chosen)

    def _save(self) -> None:
        self.saved.emit(self.output_dir.text().strip(), self.concurrent.value())
        self.engines_saved.emit([box.settings() for box in self._engine_boxes])

    def apply_icons(self) -> None:
        self.save_btn.setIcon(icon("check", "#ffffff"))
        self.save_btn.setIconSize(QSize(16, 16))
        for index, (key, _label) in enumerate(THEME_LABELS.items()):
            self.theme.setItemIcon(index, icon(THEME_ICONS[key]))
        self.theme.setIconSize(QSize(16, 16))
        for box in self._engine_boxes:
            box.apply_icons()
