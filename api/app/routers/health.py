from __future__ import annotations

from fastapi import APIRouter, Response, status

from ..config import get_settings
from ..database import check_database, state

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(response: Response):
    settings = get_settings()
    database_ok = check_database()
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "ok": database_ok,
        "service": settings.app_name,
        "version": settings.app_version,
        "mode": "review-queue",
        "database": {
            "ready": state.ready,
            "detail": state.detail,
            "checked_at": state.checked_at.isoformat() if state.checked_at else None,
        },
    }


@router.get("/live")
def liveness():
    settings = get_settings()
    return {"ok": True, "service": settings.app_name, "version": settings.app_version}


@router.get("/ready")
def readiness(response: Response):
    database_ok = check_database()
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ok": database_ok, "database": state.detail}
