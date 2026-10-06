"""Engine auto-update: stable GitHub releases → app-data bin/, verified.

Policy (arch §5.3/§9):
- Only engines with source=auto are ever touched (system/PATH are respected).
- Stable channel only; auto_update setting can disable.
- Downloads go to `<app-data>/bin/<binary>` and are replaced atomically.
- SHA256 from the release's SHA2-256SUMS is mandatory; mismatch aborts.
- Host allowlist + HTTPS only.

Pure helpers (version_key, is_newer, parse_checksums, asset_name_for) are
unit-tested; the network state machine is exercised manually.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from ytpaw.infra import timing

if TYPE_CHECKING:
    from ytpaw.domain.engines_base import Engine

ALLOWED_HOSTS = {"api.github.com", "github.com", "objects.githubusercontent.com"}
TIMEOUT_MS = 90_000


def version_key(value: str) -> tuple[int, ...]:
    parts = re.split(r"[.\-+_]", value.strip())
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


def is_newer(latest: str, current: str | None) -> bool:
    if not latest:
        return False
    if not current or current in ("unknown", ""):
        return True
    return version_key(latest) > version_key(current)


def parse_checksums(text: str, asset_name: str) -> str | None:
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].lstrip("*") == asset_name:
            candidate = parts[0].strip().lower()
            if re.fullmatch(r"[0-9a-f]{64}", candidate):
                return candidate
    return None


def asset_name_for(engine: Engine) -> str:
    return engine.binary_name + (".exe" if os.name == "nt" else "")


class EngineUpdater(QObject):
    updated = Signal(str, str, str)  # engine_id, old_version, new_version
    failed = Signal(str, str)  # engine_id, message
    finished = Signal(str)  # engine_id — always emitted when a run ends
    progress = Signal(str, int, int)  # engine_id, received, total (-1 unknown)
    waiting = Signal(str)  # engine_id — downloaded, waiting to install

    def __init__(self, bin_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bin_dir = bin_dir
        self._bin_dir.mkdir(parents=True, exist_ok=True)
        self._nam = QNetworkAccessManager(self)
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(lambda: self._fail("update timed out"))
        self._install_timer = QTimer(self)
        self._install_timer.setSingleShot(True)
        self._install_timer.timeout.connect(self._try_install)
        # Windows connect stalls are ~21s (SYN timeout); retry early with a
        # fresh connection, which usually wins the race.
        self._stall_timer = QTimer(self)
        self._stall_timer.setSingleShot(True)
        self._stall_timer.timeout.connect(self._on_asset_stall)
        self._asset_retries = 0
        self._suppress_error = False
        self._engine: Engine | None = None
        self._reply: QNetworkReply | None = None
        self._current = ""
        self._tag = ""
        self._sums = ""
        self._asset = ""
        self._checksum: str | None = None
        self._busy = False
        self._aborting = False
        self._req_t0 = 0.0
        self._req_first = False
        self._is_engine_active: Callable[[str], bool] | None = None
        self._pending: tuple[Engine, str, Path, Path] | None = None
        self._install_attempts = 0

    @property
    def busy(self) -> bool:
        return self._busy

    def set_busy_checker(self, checker: Callable[[str], bool]) -> None:
        """Callback: is a job currently running with this engine's binary?"""
        self._is_engine_active = checker

    def abort(self) -> None:
        """Clean shutdown: drop any in-flight request without signals."""
        self._aborting = True
        if self._reply is not None:
            self._reply.abort()
        temp = self._pending[3] if self._pending else None
        if temp is not None:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
        self._reset()

    def update(self, engine: Engine, current_version: str | None) -> None:
        if self._busy:
            return
        self._busy = True
        self._aborting = False
        self._engine = engine
        self._current = current_version or ""
        repo = getattr(engine, "update_repo", "")
        if not repo:
            self._fail("no update repository configured")
            return
        self._watchdog.start(TIMEOUT_MS)
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        self._get(url, self._on_latest)

    # ---------- stages ----------

    def _on_latest(self, reply: QNetworkReply) -> None:
        if not self._check_reply(reply):
            return
        try:
            data = json.loads(bytes(reply.readAll().data()) or b"{}")
        except ValueError:
            self._fail("could not parse release metadata")
            return
        tag = str(data.get("tag_name") or "")
        if not tag:
            self._fail("release metadata has no tag")
            return
        if not is_newer(tag, self._current):
            engine_id = self._engine.engine_id if self._engine else "?"
            self._reset()
            self.finished.emit(engine_id)  # already up to date, silent
            return
        self._tag = tag
        if self._engine is None:
            return
        self._asset = asset_name_for(self._engine)
        # Fast path: the release JSON carries a per-asset sha256 digest.
        # The SHA2-256SUMS file endpoint frequently stalls 20s+ on GitHub,
        # so only fall back to it when the digest is absent.
        digest = self._asset_digest(data, self._asset)
        if digest is not None:
            self._checksum = digest
            self._download_asset()
            return
        repo = self._engine.update_repo
        sums_url = f"https://github.com/{repo}/releases/download/{tag}/SHA2-256SUMS"
        self._get(sums_url, self._on_sums)

    @staticmethod
    def _asset_digest(data: dict[str, object], asset_name: str) -> str | None:
        assets = data.get("assets")
        if not isinstance(assets, list):
            return None
        for asset in assets:
            if not isinstance(asset, dict) or asset.get("name") != asset_name:
                continue
            digest = str(asset.get("digest") or "")
            if digest.startswith("sha256:"):
                value = digest.split(":", 1)[1].strip().lower()
                if re.fullmatch(r"[0-9a-f]{64}", value):
                    return value
        return None

    def _download_asset(self) -> None:
        if self._engine is None:
            return
        repo = self._engine.update_repo
        asset_url = (
            f"https://github.com/{repo}/releases/download/{self._tag}/{self._asset}"
        )
        self._get(asset_url, self._on_asset, track_progress=True)
        self.progress.emit(self._engine.engine_id, 0, 0)  # banner: downloading…
        self._stall_timer.start(8000)  # no bytes within 8s → retry

    def _on_asset_stall(self) -> None:
        if self._engine is None:
            return
        if self._asset_retries >= 1:
            self._suppress_error = True
            if self._reply is not None:
                self._reply.abort()
            self._fail(f"{self._asset} download stalled twice")
            return
        self._asset_retries += 1
        timing.note("asset stalled 8s → retrying with a fresh connection")
        self._suppress_error = True
        if self._reply is not None:
            self._reply.abort()
        self._download_asset()

    def _on_sums(self, reply: QNetworkReply) -> None:
        if not self._check_reply(reply):
            return
        if self._engine is None:
            return
        self._sums = bytes(reply.readAll().data()).decode("utf-8", "replace")
        self._asset = asset_name_for(self._engine)
        if parse_checksums(self._sums, self._asset) is None:
            self._fail(f"no checksum published for {self._asset}")
            return
        self._download_asset()

    def _on_asset(self, reply: QNetworkReply) -> None:
        if not self._check_reply(reply):
            return
        self._stall_timer.stop()
        if self._engine is None:
            return
        data = bytes(reply.readAll().data())
        expected = self._checksum or parse_checksums(self._sums, self._asset)
        digest = hashlib.sha256(data).hexdigest()
        if expected is None or digest != expected:
            self._fail("checksum mismatch — update aborted")
            return
        target = self._bin_dir / self._asset
        temp = self._bin_dir / (self._asset + ".new")
        try:
            temp.write_bytes(data)
            if os.name != "nt":
                os.chmod(temp, 0o755)
        except OSError as exc:
            self._fail(f"could not stage binary: {exc}")
            return
        self._pending = (self._engine, self._current or "none", temp, target)
        self._install_attempts = 0
        self._watchdog.stop()  # download done; install timer governs from here
        self._try_install()

    def _try_install(self) -> None:
        """Atomic swap, deferred while the engine binary is in use."""
        if self._pending is None:
            return
        engine, old, temp, target = self._pending
        engine_id = engine.engine_id
        if self._is_engine_active is not None and self._is_engine_active(engine_id):
            if self._install_attempts == 0:
                self.waiting.emit(engine_id)
            self._install_attempts += 1
            if self._install_attempts > 150:  # ~5 min at 2s
                self._fail("engine stayed busy; update postponed")
                return
            self._install_timer.start(2000)
            return
        try:
            os.replace(temp, target)
        except OSError:
            # Windows may still hold the file briefly after a job ends.
            self._install_attempts += 1
            if self._install_attempts > 30:
                self._fail("could not replace engine binary (file in use)")
                return
            self._install_timer.start(2000)
            return
        new_version = engine.probe_version(str(target))
        self._pending = None
        self._reset()
        self.updated.emit(engine_id, old, new_version)
        self.finished.emit(engine_id)

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
        if "api.github.com" in url:
            request.setRawHeader(b"Accept", b"application/vnd.github+json")
        reply = self._nam.get(request)
        self._reply = reply
        self._req_t0 = timing.now()
        self._req_first = False
        timing.note(f"GET {url}")
        if track_progress:
            engine_id = self._engine.engine_id if self._engine else "?"
            reply.downloadProgress.connect(
                lambda received, total: self._on_download_progress(
                    engine_id, received, total
                )
            )
        reply.finished.connect(lambda: handler(reply))

    def _on_download_progress(self, engine_id: str, received: int, total: int) -> None:
        if not self._req_first:
            self._req_first = True
            self._stall_timer.stop()
            timing.log("first bytes of asset received", self._req_t0)
        self.progress.emit(engine_id, received, total)

    def _check_reply(self, reply: QNetworkReply) -> bool:
        if self._suppress_error:  # intentional abort (retry); swallow result
            self._suppress_error = False
            self._stall_timer.stop()
            reply.deleteLater()
            return False
        if reply is self._reply:
            self._reply = None
        if self._aborting:  # shutdown: swallow late abort signals
            reply.deleteLater()
            return False
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        message = reply.errorString()
        reply.deleteLater()
        if ok:
            timing.log("reply complete", self._req_t0)
        if not ok:
            self._fail(f"network error: {message}")
        return ok

    def _fail(self, message: str) -> None:
        engine_id = self._engine.engine_id if self._engine else "?"
        if self._pending is not None:
            try:
                self._pending[3].unlink(missing_ok=True)
            except OSError:
                pass
            self._pending = None
        self._reset()
        self.failed.emit(engine_id, message)
        self.finished.emit(engine_id)

    def _reset(self) -> None:
        self._watchdog.stop()
        self._install_timer.stop()
        self._stall_timer.stop()
        self._asset_retries = 0
        self._suppress_error = False
        self._busy = False
        self._engine = None
        self._reply = None
        self._tag = ""
        self._sums = ""
        self._asset = ""
        self._checksum = None
