from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from ..config import get_settings


def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    expected = get_settings().admin_api_key
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured.")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=401, detail="Invalid administrator key.")
