from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from ..config import get_settings

_windows: dict[str, deque[float]] = defaultdict(deque)
_analytics_windows: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(request: Request) -> str:
    settings = get_settings()
    ip = client_ip(request)
    now = time.time()
    window = _windows[ip]
    while window and window[0] < now - 3600:
        window.popleft()
    if len(window) >= settings.max_requests_per_hour:
        raise HTTPException(status_code=429, detail="Submission limit reached. Please try again later.")
    window.append(now)
    return hashlib.sha256(f"{settings.ip_hash_salt}:{ip}".encode("utf-8")).hexdigest()


def enforce_analytics(request: Request) -> None:
    """Bound anonymous telemetry noise without persisting the visitor's IP."""
    settings = get_settings()
    ip = client_ip(request)
    rate_key = hashlib.sha256(
        f"analytics-rate:{settings.ip_hash_salt}:{ip}".encode("utf-8")
    ).hexdigest()
    now = time.time()
    window = _analytics_windows[rate_key]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= settings.analytics_max_events_per_minute:
        raise HTTPException(status_code=429, detail="Analytics event limit reached.")
    window.append(now)
