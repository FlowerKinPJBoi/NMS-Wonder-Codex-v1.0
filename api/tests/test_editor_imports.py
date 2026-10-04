import base64
import copy
import os
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (AssetSpecimen, CaptureAppConnection, Discovery, EditorAppConnection, EditorImportReceipt,
                        SubmissionBatch, SubmittedDiscovery, SubmittedPetMatch, UserProfile, AuditEvent)
from app.routers import editor_auth, editor_imports
from app.services import editor_auth as auth_service
from app.services.editor_imports import DiscoveryRecord, normalized_discovery
from test_capture_passport import passport  # isolated database, fake JWTs, no live network


@pytest.fixture
def editor(passport, monkeypatch):
    client, engine, auth, now = passport
    monkeypatch.setattr(auth_service, "now_utc", lambda: now[0])
    monkeypatch.setattr(editor_auth, "now_utc", lambda: now[0])
    monkeypatch.setattr(auth_service, "check_database", lambda: True)
    monkeypatch.setattr(editor_imports, "check_database", lambda: True)
    # The optional CI Postgres database persists across tests; these are only test rows.
    with Session(engine) as session:
        for model in (EditorImportReceipt, EditorAppConnection, SubmittedPetMatch, SubmittedDiscovery,
                      AssetSpecimen, AuditEvent, SubmissionBatch):
            session.execute(delete(model))
        session.commit()
    return passport


def start(client):
    response = client.post("/auth/editor/start")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def connect(editor, subject="tester"):
    client, _, auth, _ = editor
    pending = start(client)
    response = client.post("/auth/editor/approve", headers=auth(subject),
                           json={"user_code": pending["user_code"], "approved": True, "code_confirmed": True})
    assert response.status_code == 200, response.text
    response = client.post("/auth/editor/token", json={"device_code": pending["device_code"]})
    assert response.status_code == 200, response.text
    token = response.json()
    assert token["status"] == "authorized" and token["scopes"] == ["import:submit"]
    return pending, token


def sample():
    return {"schema": "wonder-codex-editor-import/1", "client_version": "WonderCodexEditor/0.4.0-alpha",
            "platform": "Steam", "public_attribution": True,
            "discoveries": [{"DT": "Animal", "UA": "0x123456789ABC", "VP": ["0xFFFFFFFFFFFFFFFF", "0x2", "0x3", "0x4"],
                             "CreatureID": "^BLOB", "CreatureType": "Blob", "Descriptors": ["^BLOB_A", "blob_a"],
                             "CustomName": "Test specimen"}],
            "assets": [{"assetType": "Multitool", "resourceFilename": "MODELS/COMMON/WEAPONS/MULTITOOL.SCENE.MBIN",
                        "seed": "0xFFFFFFFFFFFFFFFF", "displayName": "Test multitool", "class": "S",
                        "sourceRole": "owned_slot", "sourceCollection": "Multitools", "sourceOrdinal": 0}]}


def submit(client, token, body=None, key=None, **headers):
    return client.post("/editor/imports", json=body or sample(), headers={
        "Authorization": "Bearer " + token["access_token"], "Idempotency-Key": key or str(uuid.uuid4()), **headers})


def test_device_flow_separates_scope_and_hashes_all_secrets(editor):
    client, engine, auth, now = editor
    pending = start(client)
    assert pending["verification_uri_complete"] == "https://wondercodex.com/account.html?editor=" + pending["user_code"]
    assert pending["device_code"] not in pending["verification_uri_complete"]
    assert client.post("/auth/editor/token", json={"device_code": pending["device_code"]}).json()["status"] == "authorization_pending"
    assert client.post("/auth/editor/token", json={"device_code": pending["device_code"]}).json()["status"] == "slow_down"
    approval = {"user_code": pending["user_code"], "approved": True, "code_confirmed": True}
    assert client.post("/auth/editor/approve", json=approval).status_code == 401
    assert client.post("/auth/editor/approve", headers=auth(), json={**approval, "code_confirmed": False}).status_code == 400
    assert client.post("/auth/capture/approve", headers=auth(), json=approval).status_code == 400
    assert client.post("/auth/editor/approve", headers=auth(), json=approval).status_code == 200
    assert client.post("/auth/editor/approve", headers=auth("other"), json=approval).status_code == 400
    now[0] += timedelta(seconds=6)
    token = client.post("/auth/editor/token", json={"device_code": pending["device_code"]}).json()
    assert token["scopes"] == ["import:submit"] and token["access_token"].startswith("wcedit_")
    assert token["public_attribution"] is False
    assert not {"email", "profile_id", "auth_subject", "nms_friend_code", "refresh_token"} & token.keys()
    with Session(engine) as session:
        row = session.scalar(select(EditorAppConnection))
        assert row.device_hash != pending["device_code"] and row.user_code_hash != pending["user_code"]
        assert row.token_hash != token["access_token"]
    headers = {"Authorization": "Bearer " + token["access_token"]}
    assert client.get("/auth/editor/session", headers=headers).status_code == 200
    assert client.get("/auth/capture/session", headers=headers).status_code == 401
    assert client.get("/account/me", headers=headers).status_code == 401
    assert client.get("/admin/apps", headers=headers).status_code in {401, 503}
    assert client.post("/auth/editor/token", json={"device_code": pending["device_code"]}).status_code == 400


@pytest.mark.parametrize("subject", ["regular", "blocked"])
def test_approval_uses_current_server_role(editor, subject):
    client, _, auth, _ = editor
    pending = start(client)
    response = client.post("/auth/editor/approve", headers=auth(subject),
                           json={"user_code": pending["user_code"], "approved": True, "code_confirmed": True})
    assert response.status_code == 403


@pytest.mark.parametrize("change", ["revoke", "cancel", "expiry", "suspend", "demote"])
def test_tokens_cannot_outlive_revocation_or_current_access(editor, change):
    client, engine, _, now = editor
    pending, token = connect(editor)
    headers = {"Authorization": "Bearer " + token["access_token"]}
    if change == "revoke":
        assert client.post("/auth/editor/revoke", headers=headers).status_code == 200
    elif change == "cancel":
        assert client.post("/auth/editor/cancel", json={"device_code": pending["device_code"]}).status_code == 200
    elif change == "expiry":
        now[0] += timedelta(hours=9)
    else:
        with Session(engine) as session:
            profile = session.get(UserProfile, "tester")
            if change == "suspend": profile.account_status = "suspended"
            else: profile.access_tier = "regular"
            session.commit()
    assert submit(client, token).status_code in {401, 403}
    assert client.post("/auth/editor/revoke", headers=headers).status_code == 200
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SubmissionBatch)) == 0


def test_capture_or_operator_token_never_authorizes_import(editor):
    client, _, auth, _ = editor
    pending = client.post("/auth/capture/start").json()
    assert client.post("/auth/capture/approve", headers=auth(), json={"user_code": pending["user_code"],
                       "approved": True, "code_confirmed": True}).status_code == 200
    capture = client.post("/auth/capture/token", json={"device_code": pending["device_code"]}).json()
    assert submit(client, capture, **{"X-Admin-Actor": "Visceral", "X-Admin-Key": "legacy-test-only"}).status_code == 401
    assert client.post("/editor/imports", json=sample(), headers={"Idempotency-Key": str(uuid.uuid4()),
                       "X-Admin-Actor": "Visceral", "X-Admin-Key": "legacy-test-only"}).status_code == 401


def test_import_derives_attribution_preserves_uint64_and_never_publishes(editor):
    client, engine, _, _ = editor
    _, token = connect(editor)
    response = submit(client, token)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["accepted"] == 2 and result["duplicates"] == result["rejected"] == 0
    assert result["public_attribution"] is False and result["pending_review"] is True
    with Session(engine) as session:
        batch = session.scalar(select(SubmissionBatch))
        row = session.scalar(select(SubmittedDiscovery))
        asset = session.scalar(select(AssetSpecimen))
        match = session.scalar(select(SubmittedPetMatch))
        assert batch.contributor == asset.contributor == "Name tester"
        assert batch.public_attribution is False and asset.public_attribution is False
        assert batch.status == "pending" and row.review_status == "pending" and asset.publication_state == "review"
        assert row.vp0 == "0xFFFFFFFFFFFFFFFF" and asset.fields["seed"] == "0xFFFFFFFFFFFFFFFF"
        assert row.raw_record["Descriptors"] == ["BLOB_A"] and match.creature_id == "BLOB"
        assert len(base64.b64decode(row.message_id)) == 40
        assert row.source_path == row.owner == "" and not asset.fields["nativeClassKnown"]
        assert session.scalar(select(func.count()).select_from(Discovery)) == 0
        assert session.scalar(select(EditorImportReceipt)).response["submission_id"] == result["submission_id"]


def test_request_retries_and_cross_profile_scope_are_idempotent(editor):
    client, engine, _, _ = editor
    _, token = connect(editor)
    key = str(uuid.uuid4())
    first = submit(client, token, key=key).json()
    again = submit(client, token, key=key).json()
    assert again == {**first, "replayed": True}
    changed = sample(); changed["assets"][0]["displayName"] = "Another name"
    assert submit(client, token, changed, key).status_code == 409
    duplicate = submit(client, token).json()
    assert duplicate["accepted"] == 0 and duplicate["duplicates"] == 2
    _, other = connect(editor, "other")
    assert submit(client, other, key=key).json()["replayed"] is False
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SubmissionBatch)) == 3
        assert session.scalar(select(func.count()).select_from(SubmittedDiscovery)) == 1
        assert session.scalar(select(func.count()).select_from(AssetSpecimen)) == 1


def test_duplicates_never_overwrite_published_assets(editor):
    client, engine, _, _ = editor
    _, token = connect(editor)
    assert submit(client, token).status_code == 200
    with Session(engine) as session:
        asset = session.scalar(select(AssetSpecimen)); asset.publication_state = "published"
        asset.display_name = "Owner reviewed name"; asset.contributor = "Original contributor"
        session.commit()
    body = sample(); body["assets"][0]["displayName"] = "Malicious overwrite"
    _, other = connect(editor, "other")
    assert submit(client, other, body).json()["duplicates"] == 2
    with Session(engine) as session:
        asset = session.scalar(select(AssetSpecimen))
        assert (asset.display_name, asset.contributor, asset.publication_state) == ("Owner reviewed name", "Original contributor", "published")


@pytest.mark.parametrize("extra", ["Owner", "Path", "AccountID", "rawSave", "Platform"])
def test_discovery_privacy_fields_are_rejected_atomically(editor, extra):
    client, engine, _, _ = editor
    _, token = connect(editor)
    body = sample(); body["discoveries"][0][extra] = "sensitive"
    assert submit(client, token, body).status_code == 422
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(EditorImportReceipt)) == 0


@pytest.mark.parametrize("change", ["float", "bool", "overflow", "address", "resourcepath", "corvette", "unknowncategory", "contributor"])
def test_invalid_data_cannot_pass_as_a_normalized_record(editor, change):
    client, _, _, _ = editor
    _, token = connect(editor)
    body = sample()
    if change == "float": body["discoveries"][0]["VP"][0] = 18446744073709551615.0
    if change == "bool": body["discoveries"][0]["VP"][0] = True
    if change == "overflow": body["discoveries"][0]["VP"][0] = "0x10000000000000000"
    if change == "address": body["discoveries"][0]["UA"] = "0xFFFFFFFFFFFFFFFF"
    if change == "resourcepath": body["assets"][0]["resourceFilename"] = "C:/Users/private/save.json"
    if change == "corvette": body["assets"][0]["resourceFilename"] = "MODELS/COMMON/SPACECRAFT/BIGGS/BIGGS.SCENE.MBIN"
    if change == "unknowncategory": body["assets"][0]["assetType"] = "InventoryItem"
    if change == "contributor": body["contributor"] = "forged admin"
    assert submit(client, token, body).status_code == 422


def test_full_vp_tail_does_not_collide_and_planet_system_need_no_projector():
    a = DiscoveryRecord(DT="SolarSystem", UA="0x123", VP=["0x1"] * 6)
    b = DiscoveryRecord(DT="SolarSystem", UA="0x123", VP=["0x1"] * 5 + ["0x2"])
    assert normalized_discovery(a)[1] != normalized_discovery(b)[1]
    assert normalized_discovery(DiscoveryRecord(DT="Planet", UA="0x123", VP=[]))[0]["MessageID"] == ""


def test_mid_import_failure_rolls_back_receipt_and_every_lane(editor, monkeypatch):
    client, engine, _, _ = editor
    _, token = connect(editor)
    original = editor_imports.insert_conflict_safe
    def failing(session, model, rows, **kwargs):
        if model is AssetSpecimen: raise RuntimeError("synthetic rollback check")
        return original(session, model, rows, **kwargs)
    monkeypatch.setattr(editor_imports, "insert_conflict_safe", failing)
    key = str(uuid.uuid4())
    with pytest.raises(RuntimeError, match="synthetic rollback check"):
        submit(client, token, key=key)
    with Session(engine) as session:
        for model in [EditorImportReceipt, SubmissionBatch, SubmittedDiscovery, SubmittedPetMatch, AssetSpecimen]:
            assert session.scalar(select(func.count()).select_from(model)) == 0
    monkeypatch.setattr(editor_imports, "insert_conflict_safe", original)
    assert submit(client, token, key=key).json()["accepted"] == 2


def test_bounded_capabilities_and_large_chunked_body(editor):
    client, _, _, _ = editor
    caps = client.get("/editor/capabilities").json()
    assert caps["schema"] == sample()["schema"] and caps["max_records"] == 10000
    _, token = connect(editor)
    body = sample(); body["discoveries"] = [body["discoveries"][0]] * 10000
    assert submit(client, token, body).status_code == 422  # plus one asset exceeds combined count
    response = client.post("/editor/imports", content=iter([b" " * 1000000] * 11),
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_xbox_platform_spelling_used_by_desktop(editor):
    client, _, _, _ = editor
    _, token = connect(editor)
    body = sample(); body["platform"] = "Xbox/Game Pass"
    assert submit(client, token, body).status_code == 200


def test_schema_not_ready_disables_auth_and_imports(editor, monkeypatch):
    client, _, _, _ = editor
    _, token = connect(editor)
    monkeypatch.setattr(auth_service, "check_database", lambda: False)
    monkeypatch.setattr(editor_imports, "check_database", lambda: False)
    assert client.get("/editor/capabilities").json()["ready"] is False
    assert client.post("/auth/editor/start").status_code == 503
    assert submit(client, token).status_code == 503


@pytest.mark.skipif(not os.environ.get("CAPTURE_AUTH_TEST_DATABASE_URL"), reason="Requires concurrent PostgreSQL transactions")
def test_concurrent_request_retries_have_one_atomic_receipt(editor):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    client, engine, _, _ = editor
    _, token = connect(editor)
    barrier, key = Barrier(2), str(uuid.uuid4())
    def run():
        barrier.wait(timeout=5)
        return submit(client, token, key=key)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert [row.status_code for row in results] == [200, 200]
    bodies = [row.json() for row in results]
    assert sorted(row["replayed"] for row in bodies) == [False, True]
    assert bodies[0]["submission_id"] == bodies[1]["submission_id"]
    with Session(engine) as session:
        for model in (EditorImportReceipt, SubmissionBatch, SubmittedDiscovery, SubmittedPetMatch, AssetSpecimen):
            assert session.scalar(select(func.count()).select_from(model)) == 1


@pytest.mark.skipif(not os.environ.get("CAPTURE_AUTH_TEST_DATABASE_URL"), reason="Requires concurrent PostgreSQL transactions")
def test_concurrent_conflicting_request_key_never_adds_second_batch(editor):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    client, engine, _, _ = editor
    _, token = connect(editor)
    barrier, key = Barrier(2), str(uuid.uuid4())
    def run(index):
        body = sample(); body["assets"][0]["displayName"] = f"Selection {index}"
        barrier.wait(timeout=5)
        return submit(client, token, body, key)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(row.status_code for row in results) == [200, 409]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(EditorImportReceipt)) == 1
        assert session.scalar(select(func.count()).select_from(SubmissionBatch)) == 1


@pytest.mark.skipif(not os.environ.get("CAPTURE_AUTH_TEST_DATABASE_URL"), reason="Requires concurrent PostgreSQL transactions")
def test_editor_code_can_issue_only_one_session_under_concurrency(editor):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    client, _, auth, _ = editor
    pending = start(client)
    assert client.post("/auth/editor/approve", headers=auth(), json={"user_code": pending["user_code"],
                       "approved": True, "code_confirmed": True}).status_code == 200
    barrier = Barrier(2)
    def run():
        barrier.wait(timeout=5)
        return client.post("/auth/editor/token", json={"device_code": pending["device_code"]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: run(), range(2)))
    assert sorted(row.status_code for row in responses) == [200, 400]
