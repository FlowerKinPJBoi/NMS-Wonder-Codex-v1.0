from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from starlette.requests import Request

from app.main import operational_http_exception, unhandled_exception
from app.models import ErrorIncident
from app.routers import analytics, daedalus
from app.services.error_incidents import create_incident, sanitized_message
from app.services.security import OperatorSession


TRAINER = OperatorSession("PJ", frozenset({"daedalus:submit"}))


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.row = None

    def add(self, value):
        self.added.append(value)

    def execute(self, *_):
        return None

    def commit(self):
        self.committed = True

    def get(self, _, incident_id):
        return self.row if self.row and self.row.id == incident_id else None


def request(path: str = "/admin/apps/daedalus/build-sessions") -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [(b"x-admin-actor", b"PJ")],
        "query_string": b"",
        "scheme": "https",
        "server": ("wondercodex.com", 443),
    })


def test_incident_messages_redact_common_secret_shapes():
    cleaned = sanitized_message(
        "OPENAI_API_KEY=sk-supersecretvalue123456 and postgres://name:password@example/db?token=abc"
    )
    assert "supersecret" not in cleaned
    assert "postgres://" not in cleaned
    assert "token=abc" not in cleaned
    assert "[redacted]" in cleaned


def test_client_504_creates_private_gateway_incident_without_prompt_or_files():
    session = FakeSession()
    payload = daedalus.DaedalusClientError(
        client_incident_id="client-12345678",
        phase="generation_request",
        http_status=504,
        elapsed_ms=60_125,
        message="Build generation failed (504)",
        source_kind="prompt_only",
        reference_count=0,
        instruction_length=78,
    )
    result = daedalus.report_client_error(payload, operator=TRAINER, session=session)
    row = session.added[0]
    assert isinstance(row, ErrorIncident)
    assert row.category == "gateway_timeout"
    assert row.actor == "PJ"
    assert row.detail["promptStored"] is False
    assert row.detail["filenamesStored"] is False
    assert row.detail["uploadedBytesStored"] is False
    assert session.committed is True
    assert result["incident_id"] == row.id


def test_owner_diagnostic_download_contains_safe_privacy_manifest():
    session = FakeSession()
    row = create_incident(
        session,
        area="daedalus",
        source="daedalus_client",
        message="Build generation failed (504)",
        status_code=504,
        actor="PJ",
    )
    row.occurred_at = datetime.now(timezone.utc)
    session.row = row
    response = analytics.download_error_diagnostic(row.id, session=session)
    payload = json.loads(response.body)
    assert response.headers["content-disposition"].endswith(f'wonder-codex-error-{row.id}.json"')
    assert payload["incident"]["category"] == "gateway_timeout"
    assert payload["privacy"]["api_keys_included"] is False
    assert payload["privacy"]["prompts_included"] is False
    assert payload["privacy"]["uploaded_file_contents_included"] is False


def test_server_http_error_returns_traceable_incident_id(monkeypatch):
    monkeypatch.setattr("app.main.record_request_error", lambda *args, **kwargs: "incident-http-123")
    response = asyncio.run(operational_http_exception(
        request(),
        HTTPException(status_code=502, detail="Model planner failed."),
    ))
    assert response.status_code == 502
    assert json.loads(response.body)["incident_id"] == "incident-http-123"
    assert response.headers["x-incident-id"] == "incident-http-123"


def test_unhandled_error_returns_safe_message_and_incident_id(monkeypatch):
    monkeypatch.setattr("app.main.record_request_error", lambda *args, **kwargs: "incident-500-123")
    response = asyncio.run(unhandled_exception(request(), RuntimeError("sensitive internal detail")))
    payload = json.loads(response.body)
    assert response.status_code == 500
    assert payload == {"detail": "Unexpected server error.", "incident_id": "incident-500-123"}
