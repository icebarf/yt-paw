"""Engine registry: the only place concrete engines are registered.

Consumers resolve engines through this module (`get_engine`, `pick_engine`,
`all_engines`). Adding an engine = implement the domain protocol + register it
here; no other core change required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ytpaw.engines import ytdlp

if TYPE_CHECKING:
    from ytpaw.domain.engines_base import Engine

_ENGINES: dict[str, Engine] = {}


def register(engine: Engine) -> None:
    _ENGINES[engine.engine_id] = engine


def unregister(engine_id: str) -> None:
    _ENGINES.pop(engine_id, None)


def all_engines() -> list[Engine]:
    return list(_ENGINES.values())


def get_engine(engine_id: str) -> Engine:
    try:
        return _ENGINES[engine_id]
    except KeyError as exc:
        raise ValueError(f"Unknown engine: {engine_id}") from exc


def pick_engine(url: str) -> str:
    """Highest can_handle() score wins; raises on unsupported URLs."""
    if not _ENGINES:
        raise ValueError("No engines registered.")
    scores = {e.engine_id: e.can_handle(url) for e in _ENGINES.values()}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] <= 0.0:
        raise ValueError(f"Unsupported URL: {url}")
    return best


register(ytdlp)
