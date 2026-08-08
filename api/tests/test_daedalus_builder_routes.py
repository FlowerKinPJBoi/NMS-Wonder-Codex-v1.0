from __future__ import annotations

import asyncio
import hashlib
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile
from starlette.requests import Request

from app.config import Settings
from app.models import DaedalusBuildJob, DaedalusBuildSession
from app.routers import daedalus
from app.services.daedalus_builder import BuildPlan
from app.services.security import OperatorSession


TRAINER = OperatorSession("PJ", frozenset({"daedalus:submit"}))


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, value):
        self.added.append(value)

    def get(self, model, value):
        return next((item for item in self.added if isinstance(item, model) and item.id == value), None)

    def scalar(self, statement):
        from app.models import DaedalusBuildPass
        return next((item for item in self.added if isinstance(item, DaedalusBuildPass)), None)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.committed = False


def source_bytes():
    objects = [
        {"Timestamp": 1, "ObjectID": "^BASE_FLAG", "UserData": 0, "Position": [0, 0, 0], "Up": [0, 1, 0], "At": [0, 0, 1]},
        {"Timestamp": 2, "ObjectID": "^F_FLOOR", "UserData": 0, "Position": [0, 0, 1], "Up": [0, 1, 0], "At": [0, 0, 1]},
    ]
    return json.dumps({"Name": "Route Test", "Objects": objects}).encode()


def build_request():
    return Request({"type": "http", "method": "POST", "path": "/admin/apps/daedalus/build-sessions", "headers": []})


def test_create_build_session_acknowledges_durable_background_job(monkeypatch):
    raw = source_bytes()
    configured = Settings(
        _env_file=None,
        openai_api_key="sk-test",
        spaces_access_key="a",
        spaces_secret_key="b",
        spaces_region="nyc3",
        spaces_bucket="private",
        spaces_endpoint="https://example.invalid",
    )
    monkeypatch.setattr(daedalus, "get_settings", lambda: configured)
    monkeypatch.setattr(daedalus, "_require_build_schema", lambda *args: None)
    monkeypatch.setattr(daedalus, "_retrieve_for_build", lambda *args: {"corpus_version": 9, "items": []})
    monkeypatch.setattr(
        daedalus,
        "start_provider_plan",
        lambda *args, **kwargs: SimpleNamespace(response_id="resp_route_test", status="queued"),
    )
    monkeypatch.setattr(
        daedalus,
        "store_build_artifact",
        lambda key, body, filename, actor: (hashlib.sha256(body).hexdigest(), len(body)),
    )
    database = FakeSession()
    upload = UploadFile(filename="Route Test.NMSBASE", file=io.BytesIO(raw))
    result = asyncio.run(daedalus.create_build_session(
        request=build_request(),
        job_id="11111111-1111-4111-8111-111111111111",
        instruction="Add a safe table.",
        source=upload,
        references=None,
        operator=TRAINER,
        session=database,
    ))
    build_session = next(item for item in database.added if isinstance(item, DaedalusBuildSession))
    build_job = next(item for item in database.added if isinstance(item, DaedalusBuildJob))
    assert database.committed is True
    assert build_session.actor == "PJ"
    assert build_session.latest_version == 0
    assert build_session.status == "generating"
    assert build_job.retrieval_snapshot["corpus_version"] == 9
    assert build_job.provider_response_id == "resp_route_test"
    assert result["job"]["status"] == "queued"


def test_reference_upload_rejects_declared_image_with_wrong_signature():
    upload = UploadFile(filename="fake.png", file=io.BytesIO(b"not an image"), headers={"content-type": "image/png"})
    with pytest.raises(HTTPException, match="does not match"):
        asyncio.run(daedalus._reference_bodies([upload], Settings(_env_file=None)))


def test_create_build_session_accepts_prompt_without_source_or_references(monkeypatch):
    configured = Settings(
        _env_file=None,
        openai_api_key="sk-test",
        spaces_access_key="a",
        spaces_secret_key="b",
        spaces_region="nyc3",
        spaces_bucket="private",
        spaces_endpoint="https://example.invalid",
    )
    captured = {}
    monkeypatch.setattr(daedalus, "get_settings", lambda: configured)
    monkeypatch.setattr(daedalus, "_require_build_schema", lambda *args: None)
    monkeypatch.setattr(daedalus, "_retrieve_for_build", lambda *args: {"corpus_version": 0, "items": []})

    def fake_start(parsed, *args, **kwargs):
        captured["parsed"] = parsed
        return SimpleNamespace(response_id="resp_prompt_only", status="in_progress")

    monkeypatch.setattr(daedalus, "start_provider_plan", fake_start)
    monkeypatch.setattr(
        daedalus,
        "store_build_artifact",
        lambda key, body, filename, actor: (hashlib.sha256(body).hexdigest(), len(body)),
    )
    database = FakeSession()
    result = asyncio.run(daedalus.create_build_session(
        request=build_request(),
        job_id="22222222-2222-4222-8222-222222222222",
        instruction='Build a sign that says "NMS 10 YEARS!" with a black backdrop and yellow lettering.',
        source=None,
        references=None,
        operator=TRAINER,
        session=database,
    ))
    build_session = next(item for item in database.added if isinstance(item, DaedalusBuildSession))
    assert captured["parsed"].origin == "prompt_bootstrap_sign"
    assert build_session.source_format == "nmsprefab"
    assert build_session.source_validation["promptOnly"] is True
    assert result["job"]["status"] == "in_progress"


def test_completed_background_job_is_validated_written_and_returned(monkeypatch):
    raw = source_bytes()
    configured = Settings(
        _env_file=None,
        openai_api_key="sk-test",
        spaces_access_key="a",
        spaces_secret_key="b",
        spaces_region="nyc3",
        spaces_bucket="private",
        spaces_endpoint="https://example.invalid",
    )
    build_session = DaedalusBuildSession(
        id="33333333-3333-4333-8333-333333333333",
        actor="PJ",
        status="generating",
        source_filename="Route Test.NMSBASE",
        source_format="nmsbase",
        source_object_key="private/source",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_size_bytes=len(raw),
        source_validation={"passed": True},
        latest_version=0,
    )
    build_job = DaedalusBuildJob(
        id="44444444-4444-4444-8444-444444444444",
        actor="PJ",
        session_id=build_session.id,
        version=1,
        base_version=0,
        status="in_progress",
        phase="model_generation",
        instruction="Add a safe table.",
        provider_response_id="resp_background_complete",
        provider_status="in_progress",
        retrieval_snapshot={"corpus_version": 9, "items": []},
        reference_count=0,
        error_incident_id="",
        error_message="",
    )
    plan = BuildPlan(summary="Safe table", assistant_message="The table is ready.", operations=[], warnings=[])
    generated = SimpleNamespace(
        body=raw,
        filename="Route-Test-Daedalus-Pass-1.nmsbase",
        plan={"schema": "wonder-codex.daedalus.build-plan.v1", "status": "APPLIED_AND_VALIDATED"},
        validation={"passed": True, "roundTripParsed": True},
        object_count=2,
        distinct_object_ids=2,
        operation_count=0,
    )
    monkeypatch.setattr(daedalus, "get_settings", lambda: configured)
    monkeypatch.setattr(daedalus, "_require_build_schema", lambda *args: None)
    monkeypatch.setattr(daedalus, "poll_provider_plan", lambda *args: SimpleNamespace(status="completed", plan=plan))
    monkeypatch.setattr(daedalus, "read_build_artifact", lambda *args, **kwargs: raw)
    monkeypatch.setattr(daedalus, "generate_build", lambda *args, **kwargs: generated)
    monkeypatch.setattr(
        daedalus,
        "store_build_artifact",
        lambda key, body, filename, actor: (hashlib.sha256(body).hexdigest(), len(body)),
    )
    database = FakeSession()
    database.add(build_session)
    database.add(build_job)
    request = Request({"type": "http", "method": "GET", "path": f"/admin/apps/daedalus/build-jobs/{build_job.id}", "headers": []})

    result = asyncio.run(daedalus.get_build_job(
        request=request,
        job_id=build_job.id,
        operator=TRAINER,
        session=database,
    ))

    assert result["job"]["status"] == "completed"
    assert result["result"]["pass"]["corpus_version"] == 9
    assert result["result"]["file_path"].endswith("/passes/1/file")
    assert build_session.latest_version == 1


def test_poll_does_not_fail_job_while_provider_acknowledgement_is_still_running(monkeypatch):
    raw = source_bytes()
    build_session = DaedalusBuildSession(
        id="55555555-5555-4555-8555-555555555555",
        actor="PJ",
        status="generating",
        source_filename="Route Test.NMSBASE",
        source_format="nmsbase",
        source_object_key="private/source",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_size_bytes=len(raw),
        source_validation={"passed": True},
        latest_version=0,
    )
    build_job = DaedalusBuildJob(
        id="66666666-6666-4666-8666-666666666666",
        actor="PJ",
        session_id=build_session.id,
        version=1,
        base_version=0,
        status="preparing",
        phase="provider_submission",
        instruction="Add a safe table.",
        provider_response_id="",
        provider_status="preparing",
        retrieval_snapshot={"corpus_version": 0, "items": []},
        reference_count=0,
        error_incident_id="",
        error_message="",
    )
    monkeypatch.setattr(daedalus, "_require_build_schema", lambda *args: None)
    database = FakeSession()
    database.add(build_session)
    database.add(build_job)
    request = Request({"type": "http", "method": "GET", "path": f"/admin/apps/daedalus/build-jobs/{build_job.id}", "headers": []})

    result = asyncio.run(daedalus.get_build_job(
        request=request,
        job_id=build_job.id,
        operator=TRAINER,
        session=database,
    ))

    assert result["job"]["status"] == "preparing"
    assert build_job.error_incident_id == ""


def test_failed_background_job_records_sanitized_incident_and_discards_prompt(monkeypatch):
    raw = source_bytes()
    build_session = DaedalusBuildSession(
        id="77777777-7777-4777-8777-777777777777",
        actor="PJ",
        status="generating",
        source_filename="Route Test.NMSBASE",
        source_format="nmsbase",
        source_object_key="private/source",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_size_bytes=len(raw),
        source_validation={"passed": True},
        latest_version=0,
    )
    build_job = DaedalusBuildJob(
        id="88888888-8888-4888-8888-888888888888",
        actor="PJ",
        session_id=build_session.id,
        version=1,
        base_version=0,
        status="in_progress",
        phase="model_generation",
        instruction="Private build prompt that must not enter the incident.",
        provider_response_id="resp_background_failed",
        provider_status="in_progress",
        retrieval_snapshot={"corpus_version": 2, "items": [{"private": "lesson"}]},
        reference_count=1,
        error_incident_id="",
        error_message="",
    )
    incident_call = {}
    monkeypatch.setattr(daedalus, "_require_build_schema", lambda *args: None)
    monkeypatch.setattr(
        daedalus,
        "poll_provider_plan",
        lambda *args: (_ for _ in ()).throw(HTTPException(status_code=502, detail="Provider ended with failed status.")),
    )
    monkeypatch.setattr(
        daedalus,
        "create_incident",
        lambda *args, **kwargs: incident_call.update(kwargs) or SimpleNamespace(id="99999999-9999-4999-8999-999999999999"),
    )
    database = FakeSession()
    database.add(build_session)
    database.add(build_job)
    request = Request({"type": "http", "method": "GET", "path": f"/admin/apps/daedalus/build-jobs/{build_job.id}", "headers": []})

    result = asyncio.run(daedalus.get_build_job(
        request=request,
        job_id=build_job.id,
        operator=TRAINER,
        session=database,
    ))

    assert result["job"]["status"] == "failed"
    assert result["job"]["error_incident_id"] == "99999999-9999-4999-8999-999999999999"
    assert build_job.instruction == ""
    assert build_job.retrieval_snapshot == {}
    assert incident_call["detail"]["promptStoredInIncident"] is False
    assert "Private build prompt" not in json.dumps(incident_call)
