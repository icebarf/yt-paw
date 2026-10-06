"""Opt-in timing logs for diagnosing slow download starts.

Enable with env var YTPAW_DEBUG_TIMING=1 (launch from a terminal to see
console output). Pure observation — no behavior change.
"""

from __future__ import annotations

import os
import time

ENABLED = os.environ.get("YTPAW_DEBUG_TIMING") == "1"


def now() -> float:
    return time.perf_counter()


def log(label: str, started: float) -> None:
    if ENABLED:
        print(f"[yt-paw timing] {label}: {time.perf_counter() - started:.2f}s", flush=True)


def note(text: str) -> None:
    if ENABLED:
        print(f"[yt-paw timing] {text}", flush=True)
