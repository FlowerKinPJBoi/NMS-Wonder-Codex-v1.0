from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from ..config import get_settings


def require_admin_key(
    x_admin_key: str | None = Header(default=None),
    x_admin_actor: str | None = Header(default=None),
) -> str:
    settings = get_settings()
    named_keys = {
        name.strip().casefold(): value
        for name, value in settings.admin_api_keys.items()
        if name.strip() and value
    }
    named_keys.update({
        name.casefold(): value.strip()
        for name, value in {
            "PJ": settings.admin_api_key_pj,
            "Boots": settings.admin_api_key_boots,
        }.items()
        if value.strip()
    })
    legacy_key = settings.admin_api_key.strip()
    if not named_keys and not legacy_key:
        raise HTTPException(status_code=503, detail="Administrator keys are not configured.")
    if not x_admin_key:
        raise HTTPException(status_code=401, detail="Invalid administrator credentials.")

    actor = (x_admin_actor or "").strip()
    expected = named_keys.get(actor.casefold()) if actor else None
    if expected and secrets.compare_digest(x_admin_key, expected):
        return actor
    if legacy_key and secrets.compare_digest(x_admin_key, legacy_key):
        return actor or "legacy-admin"
    raise HTTPException(status_code=401, detail="Invalid administrator credentials.")
