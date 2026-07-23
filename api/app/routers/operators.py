from __future__ import annotations

from fastapi import APIRouter, Depends

from ..services.security import OperatorSession, require_operator_key


router = APIRouter(prefix="/operator", tags=["operator"])


@router.get("/session")
def operator_session(operator: OperatorSession = Depends(require_operator_key)):
    """Return only the authenticated operator's non-secret capability set."""
    return {
        "operator": operator.actor,
        "scopes": sorted(operator.scopes),
        "is_admin": "admin" in operator.scopes,
    }
