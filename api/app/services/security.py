from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import Header, HTTPException

from ..config import get_settings


@dataclass(frozen=True)
class OperatorSession:
    actor: str
    scopes: frozenset[str]

    @property
    def can_upload_private_apps(self) -> bool:
        return "admin" in self.scopes


def _cleaned_keys(values: dict[str, str]) -> dict[str, tuple[str, str]]:
    return {
        name.strip().casefold(): (name.strip(), value.strip())
        for name, value in values.items()
        if name.strip() and value.strip()
    }


def _configured_admin_keys() -> dict[str, tuple[str, str]]:
    settings = get_settings()
    values = dict(settings.admin_api_keys)
    if settings.admin_api_key_pj.strip():
        values["PJ"] = settings.admin_api_key_pj
    if settings.admin_api_key_boots.strip():
        values["Boots"] = settings.admin_api_key_boots
    return _cleaned_keys(values)


def _authenticate(
    x_admin_key: str | None,
    x_admin_actor: str | None,
    *,
    include_testers: bool,
) -> OperatorSession:
    settings = get_settings()
    admin_keys = _configured_admin_keys()
    tester_keys = _cleaned_keys(settings.tester_api_keys) if include_testers else {}
    legacy_key = settings.admin_api_key.strip()
    if not admin_keys and not tester_keys and not legacy_key:
        raise HTTPException(status_code=503, detail="Operator keys are not configured.")
    if not x_admin_key:
        raise HTTPException(status_code=401, detail="Invalid operator credentials.")

    actor = (x_admin_actor or "").strip()
    lookup = actor.casefold()
    admin = admin_keys.get(lookup) if actor else None
    if admin and secrets.compare_digest(x_admin_key, admin[1]):
        return OperatorSession(admin[0], frozenset({"admin", "apps:download", "apps:upload", "transit"}))

    tester = tester_keys.get(lookup) if actor else None
    if tester and secrets.compare_digest(x_admin_key, tester[1]):
        return OperatorSession(tester[0], frozenset({"apps:download", "transit"}))

    if legacy_key and secrets.compare_digest(x_admin_key, legacy_key):
        return OperatorSession(actor or "legacy-admin", frozenset({"admin", "apps:download", "apps:upload", "transit"}))
    raise HTTPException(status_code=401, detail="Invalid operator credentials.")


def require_admin_key(
    x_admin_key: str | None = Header(default=None),
    x_admin_actor: str | None = Header(default=None),
) -> str:
    return _authenticate(x_admin_key, x_admin_actor, include_testers=False).actor


def require_operator_key(
    x_admin_key: str | None = Header(default=None),
    x_admin_actor: str | None = Header(default=None),
) -> OperatorSession:
    """Authorize full admins or restricted private-app/transit testers."""
    return _authenticate(x_admin_key, x_admin_actor, include_testers=True)
