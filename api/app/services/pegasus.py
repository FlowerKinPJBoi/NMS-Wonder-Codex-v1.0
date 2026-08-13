from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from ..config import get_settings
from ..models import Discovery, PegasusDispatch, UserProfile
from .accounts import decrypt_friend_code
from .catalog import display_name, serialize_discovery, wc_id


PEGASUS_REQUESTER_TIERS = frozenset({"admin", "tester"})
PEGASUS_ACTIVE_STATUSES = frozenset({
    "queued",
    "claimed",
    "preparing",
    "waiting_for_game_exit",
    "save_written",
    "launching",
    "boarding",
})
PEGASUS_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "expired"})


def require_live_requester(profile: UserProfile) -> UserProfile:
    if profile.access_tier not in PEGASUS_REQUESTER_TIERS:
        raise HTTPException(status_code=403, detail="Pegasus Live is currently limited to Admin and Tester Passports.")
    if not profile.bot_connect_consent:
        raise HTTPException(status_code=409, detail="Enable Wonder Bot connection consent in your Passport first.")
    if not profile.nms_friend_code_encrypted:
        raise HTTPException(status_code=409, detail="Add your NMS friend code to your Passport first.")
    return profile


def destination_for(discovery: Discovery) -> dict[str, Any]:
    route = serialize_discovery(discovery)
    if not route["has_travel_address"]:
        raise HTTPException(status_code=409, detail="This Wonder record does not have a complete Pegasus route yet.")
    galaxy_number = int(route["galaxy_number"] or 0)
    glyphs = str(route["portal_glyphs"] or "").upper()
    if galaxy_number < 1 or galaxy_number > 256 or len(glyphs) != 12:
        raise HTTPException(status_code=409, detail="This Wonder record's travel address is not safe to dispatch.")
    universal_address = f"0x{route['ua_normalized']}" if route["ua_normalized"] else str(route["ua"] or "")
    return {
        "wc_record_id": wc_id(discovery),
        "destination_name": display_name(discovery),
        "galaxy_number": galaxy_number,
        "galaxy_name": str(route["galaxy_name"] or ""),
        "portal_glyphs": glyphs,
        "universal_address": universal_address,
    }


def serialize_dispatch(dispatch: PegasusDispatch) -> dict[str, Any]:
    return {
        "id": dispatch.id,
        "created_at": dispatch.created_at.isoformat() if dispatch.created_at else None,
        "updated_at": dispatch.updated_at.isoformat() if dispatch.updated_at else None,
        "expires_at": dispatch.expires_at.isoformat() if dispatch.expires_at else None,
        "completed_at": dispatch.completed_at.isoformat() if dispatch.completed_at else None,
        "status": dispatch.status,
        "phase": dispatch.phase,
        "message": dispatch.status_message,
        "requester": {
            "name": dispatch.requester_name,
            "tier": dispatch.requester_tier,
        },
        "route": {
            "discovery_id": dispatch.discovery_id,
            "wc_record_id": dispatch.wc_record_id,
            "destination_name": dispatch.destination_name,
            "galaxy_number": dispatch.galaxy_number,
            "galaxy_name": dispatch.galaxy_name,
            "portal_glyphs": dispatch.portal_glyphs,
            "universal_address": dispatch.universal_address,
        },
    }


def serialize_requester_dispatch(dispatch: PegasusDispatch) -> dict[str, Any]:
    payload = serialize_dispatch(dispatch)
    payload["host"] = {
        "name": "Pegasus",
        "nms_friend_code": get_settings().pegasus_nms_friend_code.strip().upper(),
    }
    return payload


def serialize_worker_dispatch(dispatch: PegasusDispatch, profile: UserProfile) -> dict[str, Any]:
    payload = serialize_dispatch(dispatch)
    payload["requester"] = {
        **payload["requester"],
        "profile_id": profile.id,
        "platform": profile.platform,
        "nms_friend_code": decrypt_friend_code(profile.nms_friend_code_encrypted),
        "bot_connect_consent": profile.bot_connect_consent,
    }
    payload["worker"] = {
        "id": dispatch.worker_id,
        "lease_expires_at": dispatch.lease_expires_at.isoformat() if dispatch.lease_expires_at else None,
        "attempt": dispatch.attempt_count,
    }
    return payload


def is_expired(dispatch: PegasusDispatch, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    return dispatch.expires_at <= current
