"""Non-engine artifact specs (JS runtime, ffmpeg, ...).

Generic shape so future engines AND dependencies are data-driven:
per-platform sources, ordered (primary → fallback), optional checksum URL.
"""

from __future__ import annotations

import platform as _platform
import sys
from dataclasses import dataclass, field


def platform_key() -> str:
    """Normalized platform id, e.g. 'windows-x86_64', 'linux-aarch64'."""
    if sys.platform.startswith("win"):
        os_name = "windows"
    elif sys.platform == "darwin":
        os_name = "darwin"
    else:
        os_name = "linux"
    machine = _platform.machine().lower()
    arch = {"amd64": "x86_64", "x64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}.get(
        machine, machine
    )
    return f"{os_name}-{arch}"


@dataclass(frozen=True)
class SourceSpec:
    """One download source. `checksum_url` text must contain the SHA-256."""
    url: str
    checksum_url: str | None = None
    archive: str = "zip"  # zip | tar.xz | raw


@dataclass(frozen=True)
class DependencySpec:
    dep_id: str
    display_name: str
    binary_name: str
    version_args: tuple[str, ...]
    sources: dict[str, tuple[SourceSpec, ...]] = field(default_factory=dict)

    def sources_for(self, key: str | None = None) -> tuple[SourceSpec, ...]:
        return self.sources.get(key or platform_key(), ())
