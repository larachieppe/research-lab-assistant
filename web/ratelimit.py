"""Minimal in-memory sliding-window rate limiter.

No Redis - this runs as a single Render free-tier instance, and losing the
counters on a restart/idle-cycle is an acceptable trade-off (same
fail-open-by-default philosophy as the rest of this app), not something
worth a new infra dependency for.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

_hits: dict[tuple[str, str], list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(max_requests: int, window_seconds: int, bucket: str):
    """FastAPI dependency factory: allow at most `max_requests` per
    `window_seconds` per client IP, scoped to `bucket` so different routes
    don't share a counter."""

    def _dependency(request: Request) -> None:
        key = (bucket, _client_ip(request))
        now = time.monotonic()
        window_start = now - window_seconds
        recent = [t for t in _hits[key] if t > window_start]
        if len(recent) >= max_requests:
            raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
        recent.append(now)
        _hits[key] = recent

    return _dependency
