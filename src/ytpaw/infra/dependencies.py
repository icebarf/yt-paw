"""Concrete dependency specs + pure helpers (testable without network).

- deno: GitHub releases (per-platform zips) + `.sha256sum` verification.
- ffmpeg: Windows primary gyan.dev essentials (verified via `.sha256`),
  fallback BtbN GitHub LGPL builds; Linux uses BtbN LGPL tar.xz.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

from ytpaw.domain.dependencies import DependencySpec, SourceSpec, platform_key

_HEX_RE = re.compile(r"\b([0-9a-fA-F]{64})\b")

DENO = DependencySpec(
    dep_id="deno",
    display_name="Deno",
    binary_name="deno",
    version_args=("--version",),
    sources={
        "windows-x86_64": (
            SourceSpec(
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-x86_64-pc-windows-msvc.zip",
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-x86_64-pc-windows-msvc.zip.sha256sum",
            ),
        ),
        "linux-x86_64": (
            SourceSpec(
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-x86_64-unknown-linux-gnu.zip",
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-x86_64-unknown-linux-gnu.zip.sha256sum",
            ),
        ),
        "linux-arm64": (
            SourceSpec(
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-aarch64-unknown-linux-gnu.zip",
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-aarch64-unknown-linux-gnu.zip.sha256sum",
            ),
        ),
        "darwin-x86_64": (
            SourceSpec(
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-x86_64-apple-darwin.zip",
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-x86_64-apple-darwin.zip.sha256sum",
            ),
        ),
        "darwin-arm64": (
            SourceSpec(
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-aarch64-apple-darwin.zip",
                "https://github.com/denoland/deno/releases/latest/download/"
                "deno-aarch64-apple-darwin.zip.sha256sum",
            ),
        ),
    },
)

_BTBN = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download"

FFMPEG = DependencySpec(
    dep_id="ffmpeg",
    display_name="FFmpeg",
    binary_name="ffmpeg",
    version_args=("-version",),
    sources={
        "windows-x86_64": (
            SourceSpec(
                "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
                "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256",
            ),
            SourceSpec(f"{_BTBN}/ffmpeg-master-latest-win64-lgpl.zip"),
        ),
        "linux-x86_64": (
            SourceSpec(f"{_BTBN}/ffmpeg-master-latest-linux64-lgpl.tar.xz"),
        ),
        "linux-arm64": (
            SourceSpec(f"{_BTBN}/ffmpeg-master-latest-linuxarm64-lgpl.tar.xz"),
        ),
    },
)

ALL_DEPENDENCIES: tuple[DependencySpec, ...] = (DENO, FFMPEG)


def parse_hash(text: str) -> str | None:
    """First 64-hex token (works for 'hash', 'hash  file', 'hash *file')."""
    match = _HEX_RE.search(text)
    return match.group(1).lower() if match else None


def extract_binary(data: bytes, binary_name: str, archive: str) -> bytes | None:
    """Find the named executable inside a zip / tar.xz and return its bytes."""
    target = binary_name + (".exe" if os.name == "nt" else "")
    if archive == "raw":
        return data
    if archive == "zip":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if Path(info.filename).name == target:
                    return zf.read(info)
        return None
    if archive == "tar.xz":
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as tf:
            for member in tf.getmembers():
                if member.isfile() and Path(member.name).name == target:
                    extracted = tf.extractfile(member)
                    return extracted.read() if extracted else None
        return None
    return None


def probe_dependency(dep: DependencySpec, binary: str) -> str | None:
    try:
        out = subprocess.run(
            [binary, *dep.version_args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    lines = out.stdout.strip().splitlines()
    return lines[0] if lines else None


def managed_binary_path(app_data: Path, dep: DependencySpec) -> Path:
    return app_data / "bin" / (dep.binary_name + (".exe" if os.name == "nt" else ""))


def system_binary_path(dep: DependencySpec) -> str | None:
    return shutil.which(dep.binary_name)


def sources_for_platform(dep: DependencySpec, key: str | None = None) -> tuple[SourceSpec, ...]:
    return dep.sources_for(key or platform_key())
