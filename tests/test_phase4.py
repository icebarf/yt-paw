"""Phase 4b gates: version compare, checksum parsing, update policy helpers."""

from __future__ import annotations

from ytpaw.engines import ytdlp
from ytpaw.infra.updater import asset_name_for, is_newer, parse_checksums, version_key

SUMS = """
abc123  yt-dlp
d41d8cd98f00b204e9800998ecf8427e  not-a-real-binary
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  yt-dlp.exe
bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb *yt-dlp_linux
"""


def test_version_key_orders_dates() -> None:
    assert version_key("2026.08.19") > version_key("2026.08.18")
    assert version_key("2026.08.19") > version_key("2025.12.31")
    assert version_key("2026.08.19") == version_key("2026.08.19")


def test_is_newer() -> None:
    assert is_newer("2026.08.19", "2026.08.18")
    assert not is_newer("2026.08.19", "2026.08.19")
    assert not is_newer("2026.08.18", "2026.08.19")
    assert is_newer("2026.08.19", None)
    assert is_newer("2026.08.19", "unknown")
    assert not is_newer("", "2026.08.19")


def test_parse_checksums() -> None:
    assert (
        parse_checksums(SUMS, "yt-dlp.exe")
        == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    # No checksum published (short hash is not valid) for this name.
    assert parse_checksums(SUMS, "yt-dlp") is None
    # Binary-mode marker "*" is accepted and lowercased.
    assert (
        parse_checksums(SUMS, "yt-dlp_linux")
        == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )
    assert parse_checksums(SUMS, "missing") is None


def test_asset_name_for_engine() -> None:
    name = asset_name_for(ytdlp)
    assert name.startswith("yt-dlp")
    assert name.endswith(".exe") or name == "yt-dlp"
