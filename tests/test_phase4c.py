"""Phase 4c gates: dependency specs, hashing, extraction, resolution."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from ytpaw.domain.dependencies import DependencySpec, SourceSpec, platform_key
from ytpaw.infra.dependencies import (
    DENO,
    FFMPEG,
    extract_binary,
    parse_hash,
    sources_for_platform,
)
from ytpaw.infra.setup_service import resolve_dependency


def test_platform_key_format() -> None:
    key = platform_key()
    assert "-" in key
    assert key.split("-")[0] in {"windows", "linux", "darwin"}


def test_deno_spec_has_platform_sources_with_checksums() -> None:
    key = platform_key()
    sources = sources_for_platform(DENO, key)
    assert sources, f"deno needs a source for {key}"
    primary = sources[0]
    assert primary.url.startswith("https://github.com/denoland/deno/")
    assert primary.checksum_url is not None
    assert primary.archive == "zip"


def test_ffmpeg_spec_windows_has_fallback() -> None:
    sources = sources_for_platform(FFMPEG, "windows-x86_64")
    assert len(sources) >= 2, "windows ffmpeg must have a fallback source"
    assert "gyan.dev" in sources[0].url
    assert sources[0].checksum_url is not None
    assert "github.com/BtbN" in sources[1].url
    assert sources[1].checksum_url is None  # optional fallback


def test_parse_hash_variants() -> None:
    h = "a" * 64
    assert parse_hash(h) == h
    assert parse_hash(f"{h}  file.zip") == h
    assert parse_hash(f"{h} *file.zip\n") == h
    assert parse_hash("no hash here") is None


def test_extract_binary_from_zip() -> None:
    buf = io.BytesIO()
    suffix = ".exe" if os.name == "nt" else ""
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "hello")
        zf.writestr(f"build/bin/tool{suffix}", b"BINARY")
    data = extract_binary(buf.getvalue(), "tool", "zip")
    assert data == b"BINARY"
    assert extract_binary(buf.getvalue(), "missing", "zip") is None
    assert extract_binary(buf.getvalue(), "tool", "raw") == buf.getvalue()


def test_resolve_dependency_missing_then_managed(tmp_path: Path) -> None:
    status = resolve_dependency(DENO, tmp_path)
    assert status.origin in {"managed", "system", "missing"}
    assert status.dep_id == "deno"

    # Place a fake managed binary: resolution must prefer it.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    name = DENO.binary_name + (".exe" if os.name == "nt" else "")
    (bin_dir / name).write_bytes(b"#!/bin/sh\n")
    managed = resolve_dependency(DENO, tmp_path)
    assert managed.origin == "managed"


def test_source_spec_defaults() -> None:
    src = SourceSpec("https://example.com/a.zip")
    assert src.archive == "zip"
    assert src.checksum_url is None


def test_dependency_spec_sources_for_unknown_platform() -> None:
    dep = DependencySpec(
        dep_id="x", display_name="X", binary_name="x", version_args=("--version",)
    )
    assert dep.sources_for("some-unknown") == ()
