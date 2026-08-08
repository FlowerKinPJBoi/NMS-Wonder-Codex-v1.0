from __future__ import annotations

import hashlib
import logging
from pathlib import PurePath
import re
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import session_scope
from ..models import ErrorIncident


logger = logging.getLogger(__name__)
SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|sess|key)-[A-Za-z0-9_-]{12,}\b", re.IGNORECASE),
    re.compile(r"\bBearer\s+\S+", re.IGNORECASE),
    re.compile(r"\b(?:postgres(?:ql)?|mysql|redis)://\S+", re.IGNORECASE),
    re.compile(r"\b(?:api[_ -]?key|password|secret|token)\b\s*[:=]\s*\S+", re.IGNORECASE),
)


def sanitized_message(value: Any, *, fallback: str = "Operational error") -> str:
    cleaned = " ".join(str(value or fallback).split())
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub("[redacted]", cleaned)
    cleaned = re.sub(
        r"([?&](?:token|key|secret|signature)=)[^&\s]+",
        r"\1[redacted]",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned[:1200] or fallback


def _clean_token(value: Any, maximum: int) -> str:
    return re.sub(r"[^A-Za-z0-9._:/+-]+", "-", str(value or "").strip())[:maximum]


def classify_status(status_code: int | None, *, source: str, exception_type: str = "") -> str:
    if status_code == 504:
        return "gateway_timeout"
    if status_code == 503:
        return "service_unavailable"
    if status_code == 502:
        return "upstream_provider"
    if status_code == 500 or exception_type:
        return "server_exception"
    if source == "daedalus_client":
        return "client_request"
    return "operational_error"


def exception_frames(exc: Exception) -> list[dict[str, Any]]:
    return [
        {
            "file": PurePath(frame.filename).name[:160],
            "line": int(frame.lineno),
            "function": frame.name[:160],
        }
        for frame in traceback.extract_tb(exc.__traceback__)[-12:]
    ]


def create_incident(
    session: Session,
    *,
    area: str,
    source: str,
    message: Any,
    status_code: int | None = None,
    actor: str = "",
    method: str = "",
    path: str = "",
    phase: str = "request",
    severity: str = "error",
    category: str = "",
    exception_type: str = "",
    detail: dict[str, Any] | None = None,
) -> ErrorIncident:
    safe_message = sanitized_message(message)
    safe_area = _clean_token(area, 40) or "api"
    safe_source = _clean_token(source, 40) or "server"
    safe_phase = _clean_token(phase, 60) or "request"
    safe_exception = _clean_token(exception_type, 160)
    safe_category = _clean_token(category, 60) or classify_status(
        status_code, source=safe_source, exception_type=safe_exception
    )
    fingerprint_source = "|".join((
        safe_area,
        safe_source,
        safe_phase,
        str(status_code or 0),
        safe_category,
        safe_exception,
        safe_message,
    ))
    row = ErrorIncident(
        id=str(uuid.uuid4()),
        area=safe_area,
        source=safe_source,
        severity=_clean_token(severity, 20) or "error",
        actor=_clean_token(actor, 120),
        method=_clean_token(method.upper(), 10),
        path=str(path or "").split("?", 1)[0][:300],
        phase=safe_phase,
        status_code=status_code,
        category=safe_category,
        exception_type=safe_exception,
        message=safe_message,
        fingerprint=hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
        detail=detail or {},
    )
    session.add(row)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, get_settings().error_retention_days))
    session.execute(delete(ErrorIncident).where(ErrorIncident.occurred_at < cutoff))
    return row


def record_request_error(request, exc: Exception, *, status_code: int, message: Any) -> str:
    path = request.url.path
    area = "daedalus" if "/daedalus" in path else "api"
    phase = str(getattr(request.state, "diagnostic_phase", "request") or "request")
    exception_type = type(exc).__name__ if status_code >= 500 else ""
    detail = {
        "frames": exception_frames(exc)
    } if status_code == 500 and not hasattr(exc, "status_code") else {}
    try:
        with session_scope() as session:
            row = create_incident(
                session,
                area=area,
                source="server",
                message=message,
                status_code=status_code,
                actor=str(getattr(request.state, "diagnostic_actor", "") or ""),
                method=request.method,
                path=path,
                phase=phase,
                severity="critical" if status_code == 500 else "error",
                exception_type=exception_type,
                detail=detail,
            )
            incident_id = row.id
        return incident_id
    except Exception:
        logger.exception("Could not persist sanitized operational error incident")
        return str(uuid.uuid4())


def incident_public(row: ErrorIncident) -> dict[str, Any]:
    return {
        "id": row.id,
        "occurred_at": row.occurred_at,
        "area": row.area,
        "source": row.source,
        "severity": row.severity,
        "actor": row.actor,
        "method": row.method,
        "path": row.path,
        "phase": row.phase,
        "status_code": row.status_code,
        "category": row.category,
        "exception_type": row.exception_type,
        "message": row.message,
        "fingerprint": row.fingerprint,
        "detail": row.detail,
    }
