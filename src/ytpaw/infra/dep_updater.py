"""Dependency downloader: platform source → fallback → SHA256 verify → extract.

Engine-agnostic artifact pipeline shared shape with the engine updater:
progress / installed / failed / finished signals, host allowlist, watchdog.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from ytpaw.domain.dependencies import DependencySpec, SourceSpec, platform_key
from ytpaw.infra.dependencies import (
    extract_binary,
    managed_binary_path,
    parse_hash,
    probe_dependency,
)

ALLOWED_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "www.gyan.dev",
}
TIMEOUT_MS = 5 * 60_000  # archives can be ~100MB


class DependencyUpdater(QObject):
    progress = Signal(str, int, int)  # dep_id, received, total
    installed = Signal(str, str)  # dep_id, version
    failed = Signal(str, str)  # dep_id, message
    finished = Signal(str)  # dep_id — always

    def __init__(self, bin_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bin_dir = bin_dir
        self._bin_dir.mkdir(parents=True, exist_ok=True)
        self._nam = QNetworkAccessManager(self)
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(lambda: self._fail("download timed out"))
        self._dep: DependencySpec | None = None
        self._sources: list[SourceSpec] = []
        self._source: SourceSpec | None = None
        self._token = 0
        self._archive = b""
        self._sum: str | None = None
        self._archive_done = False
        self._sums_done = False
        self._reply: QNetworkReply | None = None
        self._busy = False
        self._aborting = False

    @property
    def busy(self) -> bool:
        return self._busy

    def abort(self) -> None:
        self._aborting = True
        if self._reply is not None:
            self._reply.abort()
        self._reset()

    def install(self, dep: DependencySpec) -> None:
        if self._busy:
            return
        self._busy = True
        self._aborting = False
        self._dep = dep
        self._sources = list(dep.sources_for(platform_key()))
        if not self._sources:
            self._fail(f"no download source for {platform_key()}")
            return
        self._watchdog.start(TIMEOUT_MS)
        self._next_source()

    # ---------- source pipeline ----------

    def _next_source(self) -> None:
        if not self._sources:
            self._fail("all download sources failed")
            return
        self._source = self._sources.pop(0)
        self._token += 1
        token = self._token
        self._archive = b""
        self._archive_done = False
        self._sums_done = self._source.checksum_url is None
        # Fetch checksum and archive concurrently: GitHub's checksum endpoints
        # can stall for 20s+, which then hides behind the actual download.
        if self._source.checksum_url:
            self._get(self._source.checksum_url, self._checksum_handler(token))
        self._get(self._source.url, self._archive_handler(token), track_progress=True)

    def _checksum_handler(self, token: int) -> Callable[[QNetworkReply], None]:
        def handler(reply: QNetworkReply) -> None:
            self._on_checksum(reply, token)

        return handler

    def _archive_handler(self, token: int) -> Callable[[QNetworkReply], None]:
        def handler(reply: QNetworkReply) -> None:
            self._on_archive(reply, token)

        return handler

    def _on_checksum(self, reply: QNetworkReply, token: int) -> None:
        if token != self._token:
            reply.deleteLater()
            return
        if not self._check_reply(reply, tolerating=True):
            self._next_source()
            return
        text = bytes(reply.readAll().data()).decode("utf-8", "replace")
        expected = parse_hash(text)
        if expected is None:
            # Unreadable checksum → don't trust an unverified source.
            self._next_source()
            return
        self._sum = expected
        self._sums_done = True
        self._maybe_install()

    def _on_archive(self, reply: QNetworkReply, token: int) -> None:
        if token != self._token:
            reply.deleteLater()
            return
        if not self._check_reply(reply, tolerating=True):
            self._next_source()
            return
        self._archive = bytes(reply.readAll().data())
        self._archive_done = True
        self._maybe_install()

    def _maybe_install(self) -> None:
        if not (self._archive_done and self._sums_done):
            return
        assert self._dep is not None and self._source is not None
        if self._source.checksum_url:
            if self._sum is None:
                self._next_source()
                return
            digest = hashlib.sha256(self._archive).hexdigest()
            if digest != self._sum:
                self._next_source()  # tampered/corrupt → try fallback
                return
        binary = extract_binary(self._archive, self._dep.binary_name, self._source.archive)
        if binary is None:
            self._next_source()
            return
        target = managed_binary_path(self._bin_dir.parent, self._dep)
        temp = target.with_suffix(target.suffix + ".new")
        try:
            temp.write_bytes(binary)
            if os.name != "nt":
                os.chmod(temp, 0o755)
            os.replace(temp, target)
        except OSError as exc:
            self._fail(f"could not install: {exc}")
            return
        version = probe_dependency(self._dep, str(target)) or "unknown"
        dep_id = self._dep.dep_id
        self._reset()
        self.installed.emit(dep_id, version)
        self.finished.emit(dep_id)

    # ---------- plumbing ----------

    def _get(
        self,
        url: str,
        handler: Callable[[QNetworkReply], None],
        track_progress: bool = False,
    ) -> None:
        parsed = QUrl(url)
        if parsed.scheme() != "https" or parsed.host() not in ALLOWED_HOSTS:
            self._fail(f"blocked non-allowlisted URL: {url}")
            return
        request = QNetworkRequest(parsed)
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        reply = self._nam.get(request)
        self._reply = reply
        if track_progress:
            dep_id = self._dep.dep_id if self._dep else "?"
            reply.downloadProgress.connect(
                lambda received, total: self.progress.emit(dep_id, received, total)
            )
        reply.finished.connect(lambda: handler(reply))

    def _check_reply(self, reply: QNetworkReply, tolerating: bool = False) -> bool:
        self._reply = None
        if self._aborting:
            reply.deleteLater()
            return False
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        reply.deleteLater()
        if not ok and not tolerating:
            self._fail("network error")
        return ok

    def _fail(self, message: str) -> None:
        dep_id = self._dep.dep_id if self._dep else "?"
        self._reset()
        self.failed.emit(dep_id, message)
        self.finished.emit(dep_id)

    def _reset(self) -> None:
        self._watchdog.stop()
        self._busy = False
        self._dep = None
        self._sources = []
        self._source = None
        self._reply = None
        self._archive = b""
        self._sum = None
        self._archive_done = False
        self._sums_done = False
