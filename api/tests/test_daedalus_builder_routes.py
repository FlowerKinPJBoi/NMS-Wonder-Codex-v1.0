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
        self.flushed = False

    def add(self, value):
        self.added.append(value)

    def get(self, model, value, **kwargs):
        return next((item for item in self.added if isinstance(item, model) and item.id == value), None)

    def scalar(self, statement):
        from app.models import DaedalusBuildPass
        return next((item for item in self.added if isinstance(item, DaedalusBuildPass)), None)

    def commit(self):
        self.committed = True

    def flush(self):
        self.flushed = True

    def rollback(self):
        self.committed = False


class ParentFirstSession(FakeSession):
    """Match the production foreign key: a new session must flush before its job."""

    def add(self, value):
        if isinstance(value, DaedalusBuildJob) and not self.flushed:
            raise AssertionError("DaedalusBuildSession must flush before DaedalusBuildJob is added")
        super().add(value)


def source_bytes():
    objects = [
        {"Timestamp": 1, "ObjectID": "^BASE_FLAG", "UserData": 0, "Position": [0, 0, 0], "Up": [0, 1, 0], "At": [0, 0, 1]},
        {"Timestamp": 2, "ObjectID": "^F_FLOOR", "UserData": 0, "Position": [0, 0, 1], "Up": [0, 1, 0], "At": [0, 0, 1]},
    ]
    return json.dumps({"Name": "Route Test", "Objects": objects}).encode()


def build_request():
    return Request({"type": "http", "method": "POST", "path": "/admin/apps/daedalus/build-sessions", "headers": []})


def reservation_request():
    return Request({"type": "http", "method": "POST", "path": "/admin/apps/daedalus/build-jobs", "headers": []})


def test_initial_job_reservation_is_durable_before_multipart_submission(monkeypatch):
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
    database = ParentFirstSession()

    result = daedalus.reserve_build_job(
        request=reservation_request(),
        reservation=daedalus.BuildJobReservation(
            job_id="10101010-1010-4010-8010-101010101010",
            instruction="Build a portable test sign.",
        ),
        operator=TRAINER,
        session=database,
    )
    retry = daedalus.reserve_build_job(
        request=reservation_request(),
        reservation=daedalus.BuildJobReservation(
            job_id="10101010-1010-4010-8010-101010101010",
            instruction="Build a portable test sign.",
        ),
        operator=TRAINER,
        session=database,
    )

    build_session = next(item for item in database.added if isinstance(item, DaedalusBuildSession))
    build_job = next(item for item in database.added if isinstance(item, DaedalusBuildJob))
    assert database.committed is True
    assert database.flushed is True
    assert build_session.actor == "PJ"
    assert build_session.status == "preparing"
    assert build_job.phase == "request_reserved"
    assert build_job.instruction == "Build a portable test sign."
    assert result["job"]["id"] == build_job.id
    assert result["job"]["session_id"] == build_session.id
    assert retry["job"]["id"] == build_job.id
    assert len([item for item in database.added if isinstance(item, DaedalusBuildJob)]) == 1
    assert len([item for item in database.added if isinstance(item, DaedalusBuildSession)]) == 1


def test_multipart_submission_claims_reserved_job_without_replacing_it(monkeypatch):
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
    monkeypatch.setattr(daedalus, "_retrieve_for_build", lambda *args: {"corpus_version": 0, "items": []})
    monkeypatch.setattr(
        daedalus,
        "start_provider_plan",
        lambda *args, **kwargs: SimpleNamespace(response_id="resp_reserved_job", status="queued"),
    )
    database = ParentFirstSession()
    daedalus.reserve_build_job(
        request=reservation_request(),
        reservation=daedalus.BuildJobReservation(
            job_id="20202020-2020-4020-8020-202020202020",
            instruction="Build a portable test sign.",
        ),
        operator=TRAINER,
        session=database,
    )
    reserved_job = next(item for item in database.added if isinstance(item, DaedalusBuildJob))
    reserved_session = next(item for item in database.added if isinstance(item, DaedalusBuildSession))
    observed = {}

    def store_source(key, body, filename, actor):
        observed["job_phase"] = reserved_job.phase
        observed["session_id"] = reserved_session.id
        return hashlib.sha256(body).hexdigest(), len(body)

    monkeypatch.setattr(daedalus, "store_build_artifact", store_source)
    result = asyncio.run(daedalus.create_build_session(
        request=build_request(),
        job_id=reserved_job.id,
        instruction="Build a portable test sign.",
        source=None,
        references=None,
        operator=TRAINER,
        session=database,
    ))

    assert len([item for item in database.added if isinstance(item, DaedalusBuildJob)]) == 1
    assert len([item for item in database.added if isinstance(item, DaedalusBuildSession)]) == 1
    assert observed == {"job_phase": "source_storage", "session_id": reserved_session.id}
    assert reserved_job.provider_response_id == "resp_reserved_job"
    assert result["job"]["status"] == "queued"


def test_revision_job_reservation_uses_the_current_immutable_pass(monkeypatch):
    from app.models import DaedalusBuildPass

    configured = Settings(
        _env_file=None,
        openai_api_key="sk-test",
        spaces_access_key="a",
        spaces_secret_key="b",
        spaces_region="nyc3",
        spaces_bucket="private",
        spaces_endpoint="https://example.invalid",
    )
    raw = source_bytes()
    build_session = DaedalusBuildSession(
        id="30303030-3030-4030-8030-303030303030",
        actor="PJ",
        status="active",
        source_filename="Route Test.NMSBASE",
        source_format="nmsbase",
        source_object_key="private/source",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_size_bytes=len(raw),
        source_validation={"passed": True},
        latest_version=1,
    )
    prior = DaedalusBuildPass(
        id="40404040-4040-4040-8040-404040404040",
        session_id=build_session.id,
        version=1,
        instruction="Initial pass.",
        output_filename="Route-Test-Daedalus-Pass-1.nmsbase",
        output_object_key="private/pass-1",
        output_sha256=hashlib.sha256(raw).hexdigest(),
        output_size_bytes=len(raw),
        object_count=2,
        distinct_object_ids=2,
        operation_count=0,
        corpus_version=0,
        model_name="gpt-5.6",
        provider_response_id="resp_previous",
        plan={"summary": "Initial"},
        validation={"passed": True},
    )

    class RevisionReservationSession(FakeSession):
        def __init__(self):
            super().__init__()
            self.scalar_calls = 0

        def scalar(self, statement):
            self.scalar_calls += 1
            return None if self.scalar_calls == 1 else prior

    database = RevisionReservationSession()
    database.add(build_session)
    database.add(prior)
    monkeypatch.setattr(daedalus, "get_settings", lambda: configured)
    monkeypatch.setattr(daedalus, "_require_build_schema", lambda *args: None)

    result = daedalus.reserve_build_job(
        request=reservation_request(),
        reservation=daedalus.BuildJobReservation(
            job_id="50505050-5050-4050-8050-505050505050",
            instruction="Revise the table.",
            session_id=build_session.id,
        ),
        operator=TRAINER,
        session=database,
    )

    build_job = next(item for item in database.added if isinstance(item, DaedalusBuildJob))
    assert database.committed is True
    assert build_session.status == "generating"
    assert build_job.session_id == build_session.id
    assert build_job.base_version == 1
    assert build_job.version == 2
    assert build_job.phase == "request_reserved"
    assert result["job"]["base_version"] == 1


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
    database = ParentFirstSession()
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
    assert database.flushed is True
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


def test_initial_job_exists_before_private_source_storage_failure(monkeypatch):
    configured = Settings(
        _env_file=None,
        openai_api_key="sk-test",
        spaces_access_key="a",
        spaces_secret_key="b",
        spaces_region="nyc3",
        spaces_bucket="private",
        spaces_endpoint="https://example.invalid",
    )
    database = FakeSession()
    observed = {}

    def fail_storage(*args, **kwargs):
        job = next(item for item in database.added if isinstance(item, DaedalusBuildJob))
        observed["job_id"] = job.id
        observed["status_during_storage"] = job.status
        observed["phase_during_storage"] = job.phase
        observed["already_committed"] = database.committed
        raise HTTPException(status_code=502, detail="Private storage test failure.")

    monkeypatch.setattr(daedalus, "get_settings", lambda: configured)
    monkeypatch.setattr(daedalus, "_require_build_schema", lambda *args: None)
    monkeypatch.setattr(daedalus, "_retrieve_for_build", lambda *args: {"corpus_version": 0, "items": []})
    monkeypatch.setattr(daedalus, "store_build_artifact", fail_storage)

    with pytest.raises(HTTPException, match="Private storage test failure"):
        asyncio.run(daedalus.create_build_session(
            request=build_request(),
            job_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            instruction="Build a portable test sign.",
            source=None,
            references=None,
            operator=TRAINER,
            session=database,
        ))

    build_job = next(item for item in database.added if isinstance(item, DaedalusBuildJob))
    build_session = next(item for item in database.added if isinstance(item, DaedalusBuildSession))
    assert observed == {
        "job_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "status_during_storage": "preparing",
        "phase_during_storage": "source_storage",
        "already_committed": True,
    }
    assert build_job.status == "failed"
    assert build_job.instruction == ""
    assert build_job.retrieval_snapshot == {}
    assert build_session.status == "failed"


def test_revision_job_exists_before_prior_pass_storage_read_failure(monkeypatch):
    from app.models import DaedalusBuildPass

    configured = Settings(
        _env_file=None,
        openai_api_key="sk-test",
        spaces_access_key="a",
        spaces_secret_key="b",
        spaces_region="nyc3",
        spaces_bucket="private",
        spaces_endpoint="https://example.invalid",
    )
    raw = source_bytes()
    build_session = DaedalusBuildSession(
        id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        actor="PJ",
        status="active",
        source_filename="Route Test.NMSBASE",
        source_format="nmsbase",
        source_object_key="private/source",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_size_bytes=len(raw),
        source_validation={"passed": True},
        latest_version=1,
    )
    prior = DaedalusBuildPass(
        id="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        session_id=build_session.id,
        version=1,
        instruction="Initial pass.",
        output_filename="Route-Test-Daedalus-Pass-1.nmsbase",
        output_object_key="private/pass-1",
        output_sha256=hashlib.sha256(raw).hexdigest(),
        output_size_bytes=len(raw),
        object_count=2,
        distinct_object_ids=2,
        operation_count=0,
        corpus_version=0,
        model_name="gpt-5.6",
        provider_response_id="resp_previous",
        plan={"summary": "Initial"},
        validation={"passed": True},
    )

    class RevisionSession(FakeSession):
        def __init__(self):
            super().__init__()
            self.scalar_calls = 0

        def scalar(self, statement):
            self.scalar_calls += 1
            return None if self.scalar_calls == 1 else prior

        def scalars(self, statement):
            return SimpleNamespace(all=lambda: [prior])

    database = RevisionSession()
    database.add(build_session)
    database.add(prior)
    observed = {}

    def fail_read(*args, **kwargs):
        job = next(item for item in database.added if isinstance(item, DaedalusBuildJob))
        observed["job_id"] = job.id
        observed["phase"] = job.phase
        observed["committed"] = database.committed
        raise HTTPException(status_code=502, detail="Prior pass storage test failure.")

    monkeypatch.setattr(daedalus, "get_settings", lambda: configured)
    monkeypatch.setattr(daedalus, "_require_build_schema", lambda *args: None)
    monkeypatch.setattr(daedalus, "read_build_artifact", fail_read)
    request = Request({"type": "http", "method": "POST", "path": f"/admin/apps/daedalus/build-sessions/{build_session.id}/passes", "headers": []})

    with pytest.raises(HTTPException, match="Prior pass storage test failure"):
        asyncio.run(daedalus.create_build_pass(
            request=request,
            session_id=build_session.id,
            job_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            instruction="Revise the table.",
            references=None,
            operator=TRAINER,
            session=database,
        ))

    build_job = next(item for item in database.added if isinstance(item, DaedalusBuildJob))
    assert observed == {
        "job_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        "phase": "artifact_read",
        "committed": True,
    }
    assert build_job.status == "failed"
    assert build_job.instruction == ""
    assert build_session.status == "active"


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
