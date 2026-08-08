from __future__ import annotations

import asyncio
import hashlib
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.config import Settings
from app.models import DaedalusBuildPass, DaedalusBuildSession
from app.routers import daedalus
from app.services.security import OperatorSession


TRAINER = OperatorSession("PJ", frozenset({"daedalus:submit"}))


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True


def source_bytes():
    objects = [
        {"Timestamp": 1, "ObjectID": "^BASE_FLAG", "UserData": 0, "Position": [0, 0, 0], "Up": [0, 1, 0], "At": [0, 0, 1]},
        {"Timestamp": 2, "ObjectID": "^F_FLOOR", "UserData": 0, "Position": [0, 0, 1], "Up": [0, 1, 0], "At": [0, 0, 1]},
    ]
    return json.dumps({"Name": "Route Test", "Objects": objects}).encode()


def test_create_build_session_persists_real_generated_pass_contract(monkeypatch):
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
    monkeypatch.setattr(daedalus, "_retrieve_for_build", lambda *args: {"corpus_version": 9, "items": []})
    generated_body = raw.replace(b"Route Test", b"Route Pass")
    generated = SimpleNamespace(
        body=generated_body,
        filename="Route-Test-Daedalus-Pass-1.nmsbase",
        sha256=hashlib.sha256(generated_body).hexdigest(),
        plan={"schema": "wonder-codex.daedalus.build-plan.v1", "status": "APPLIED_AND_VALIDATED"},
        validation={"passed": True, "protectedAnchorExact": True, "roundTripParsed": True},
        object_count=2,
        distinct_object_ids=2,
        operation_count=1,
        provider_response_id="resp_route_test",
    )
    monkeypatch.setattr(daedalus, "generate_build", lambda *args, **kwargs: generated)
    monkeypatch.setattr(
        daedalus,
        "store_build_artifact",
        lambda key, body, filename, actor: (hashlib.sha256(body).hexdigest(), len(body)),
    )
    database = FakeSession()
    upload = UploadFile(filename="Route Test.NMSBASE", file=io.BytesIO(raw))
    result = asyncio.run(daedalus.create_build_session(
        instruction="Add a safe table.",
        source=upload,
        references=None,
        operator=TRAINER,
        session=database,
    ))
    build_session = next(item for item in database.added if isinstance(item, DaedalusBuildSession))
    build_pass = next(item for item in database.added if isinstance(item, DaedalusBuildPass))
    assert database.committed is True
    assert build_session.actor == "PJ"
    assert build_session.latest_version == 1
    assert build_pass.corpus_version == 9
    assert build_pass.provider_response_id == "resp_route_test"
    assert result["pass"]["validation"]["roundTripParsed"] is True
    assert result["file_path"].endswith("/passes/1/file")


def test_reference_upload_rejects_declared_image_with_wrong_signature():
    upload = UploadFile(filename="fake.png", file=io.BytesIO(b"not an image"), headers={"content-type": "image/png"})
    with pytest.raises(HTTPException, match="does not match"):
        asyncio.run(daedalus._reference_bodies([upload], Settings(_env_file=None)))
