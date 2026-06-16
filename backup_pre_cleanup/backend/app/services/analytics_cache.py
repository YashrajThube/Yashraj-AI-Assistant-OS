from __future__ import annotations

import time
from typing import Any

_CACHE_TTL_SECONDS = 30
_ANALYTICS_CACHE: dict[int, tuple[float, dict[str, Any]]] = {}


def get_cached_analytics(user_id: int) -> dict[str, Any] | None:
    cached = _ANALYTICS_CACHE.get(user_id)
    if cached is None:
        return None

    expires_at, payload = cached
    if expires_at < time.time():
        _ANALYTICS_CACHE.pop(user_id, None)
        return None

    return payload


def set_cached_analytics(user_id: int, payload: dict[str, Any]) -> None:
    _ANALYTICS_CACHE[user_id] = (time.time() + _CACHE_TTL_SECONDS, payload)


def invalidate_cached_analytics(user_id: int | None = None) -> None:
    if user_id is None:
        _ANALYTICS_CACHE.clear()
        return
    _ANALYTICS_CACHE.pop(user_id, None)
