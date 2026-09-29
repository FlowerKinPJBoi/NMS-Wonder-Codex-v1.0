import io
import os
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, delete, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_session
from app.main import app
from app.models import CaptureAppConnection, CaptureAuthRateWindow, CaptureSubmission, UserProfile
from app.routers import capture_auth, captures
from app.services import capture_auth as service


@compiles(JSONB, "sqlite")
def sqlite_jsonb(_type, _compiler, **_kw):
    return "JSON"


@pytest.fixture
def passport(monkeypatch):
    monkeypatch.setenv("AUTH_SUPABASE_URL", "https://auth.example.invalid")
    monkeypatch.setenv("AUTH_SUPABASE_ANON_KEY", "public-test-key")
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-only-signing-key-not-a-real-secret")
    monkeypatch.setenv("TESTER_API_KEY_VISCERAL", "legacy-test-only")
    get_settings.cache_clear()
    test_url = os.environ.get("CAPTURE_AUTH_TEST_DATABASE_URL", "")
    if test_url:
        engine = create_engine(test_url)
        with Session(engine) as session:
            for model in (CaptureSubmission, CaptureAppConnection, CaptureAuthRateWindow, UserProfile):
                session.execute(delete(model))
            session.commit()
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
    now = [datetime.now(timezone.utc)]
    monkeypatch.setattr(service, "now_utc", lambda: now[0])
    monkeypatch.setattr(capture_auth, "now_utc", lambda: now[0])
    monkeypatch.setattr(captures, "check_database", lambda: True)
    monkeypatch.setattr(captures, "put_pending", lambda *_args: None)

    def database():
        with Session(engine) as session:
            yield session

    original = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = database
    client = TestClient(app)
    with Session(engine) as session:
        for subject, tier, status in [("tester", "tester", "active"), ("other", "tester", "active"),
                                      ("regular", "regular", "active"), ("blocked", "tester", "suspended")]:
            session.add(UserProfile(id=subject, auth_subject=subject, contributor_name=f"Name {subject}",
                                    access_tier=tier, account_status=status, public_attribution=False))
        session.commit()

    def auth(subject="tester", **claims):
        values = {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                  "iss": "https://auth.example.invalid/auth/v1", "aud": "authenticated",
                  "user_metadata": {"access_tier": "admin"}}
        values.update(claims)
        value = jwt.encode(values, get_settings().auth_jwt_secret, algorithm="HS256")
        return {"Authorization": f"Bearer {value}"}

    yield client, engine, auth, now
    client.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original)
    engine.dispose()
    get_settings.cache_clear()


def start(client):
    response = client.post("/auth/capture/start")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def approve(client, request, auth, **values):
    return client.post("/auth/capture/approve", headers=auth,
                       json={"user_code": request["user_code"], "approved": True, "code_confirmed": True, **values})


def exchange(client, request):
    return client.post("/auth/capture/token", json={"device_code": request["device_code"]})


def connect(passport):
    client, _, auth, _ = passport
    request = start(client)
    assert approve(client, request, auth()).status_code == 200
    response = exchange(client, request)
    assert response.status_code == 200, response.text
    return request, response.json()


def test_browser_approval_is_required_once_and_secrets_are_hashed(passport):
    client, engine, auth, now = passport
    request = start(client)
    assert request["verification_uri_complete"] == "https://wondercodex.com/account.html?capture=" + request["user_code"]
    assert request["device_code"] not in request["verification_uri_complete"]
    assert exchange(client, request).json()["status"] == "authorization_pending"
    assert exchange(client, request).json()["status"] == "slow_down"
    assert approve(client, request, {}).status_code == 401
    assert approve(client, request, auth(), code_confirmed=False).status_code == 400
    assert approve(client, request, auth()).status_code == 200
    assert approve(client, request, auth("other")).status_code == 400
    now[0] += timedelta(seconds=6)
    result = exchange(client, request).json()
    assert result["scopes"] == ["capture:submit"]
    assert result["contributor_name"] == "Name tester"
    assert result["public_attribution"] is False
    assert not {"profile_id", "auth_subject", "email", "nms_friend_code", "refresh_token"} & result.keys()
    with Session(engine) as session:
        row = session.scalar(select(CaptureAppConnection))
        assert row.device_hash != request["device_code"]
        assert row.user_code_hash != request["user_code"]
        assert row.token_hash != result["access_token"]
    assert exchange(client, request).status_code == 400
    headers = {"Authorization": "Bearer " + result["access_token"]}
    assert client.get("/auth/capture/session", headers=headers).json()["contributor_name"] == "Name tester"
    assert client.get("/account/me", headers=headers).status_code == 401
    assert client.get("/operator/session", headers=headers).status_code in {401, 503}


@pytest.mark.parametrize("subject", ["regular", "blocked"])
def test_permissions_use_server_profile_not_user_metadata(passport, subject):
    client, _, auth, _ = passport
    request = start(client)
    assert approve(client, request, auth(subject)).status_code == 403
    assert exchange(client, request).json()["status"] == "authorization_pending"


def test_invalid_expired_wrong_issuer_and_audience_passports_rejected(passport):
    client, _, auth, _ = passport
    request = start(client)
    for headers in [auth(exp=1), auth(iss="https://wrong.invalid/auth/v1"), auth(aud="anon"),
                    {"Authorization": "Bearer broken"}]:
        assert approve(client, request, headers).status_code == 401


def test_decline_cancel_expiry_and_approval_replay(passport):
    client, _, auth, now = passport
    declined = start(client)
    assert approve(client, declined, auth(), approved=False).status_code == 200
    assert exchange(client, declined).status_code == 403
    cancelled = start(client)
    assert client.post("/auth/capture/cancel", json={"device_code": cancelled["device_code"]}).status_code == 200
    assert approve(client, cancelled, auth()).status_code == 400
    assert exchange(client, cancelled).status_code == 400
    expired = start(client)
    now[0] += timedelta(minutes=11)
    assert approve(client, expired, auth()).status_code == 400
    assert exchange(client, expired).status_code == 400


@pytest.mark.parametrize("change", ["revoke", "cancel", "expiry", "suspend", "demote"])
def test_session_revocation_and_current_profile_access(passport, change):
    client, engine, _, now = passport
    request, result = connect(passport)
    headers = {"Authorization": "Bearer " + result["access_token"]}
    if change == "revoke":
        assert client.post("/auth/capture/revoke", headers=headers).status_code == 200
    elif change == "cancel":
        assert client.post("/auth/capture/cancel", json={"device_code": request["device_code"]}).status_code == 200
    elif change == "expiry":
        now[0] += timedelta(hours=9)
    else:
        with Session(engine) as session:
            profile = session.get(UserProfile, "tester")
            if change == "suspend": profile.account_status = "suspended"
            else: profile.access_tier = "regular"
            session.commit()
    assert client.get("/auth/capture/session", headers=headers).status_code in {401, 403}
    assert client.post("/auth/capture/revoke", headers=headers).status_code == 200


def test_rate_limits_cover_creation_and_approval_guesses(passport):
    client, _, auth, _ = passport
    request = start(client)
    for _ in range(19): start(client)
    assert client.post("/auth/capture/start").status_code == 429
    for _ in range(30):
        response = approve(client, {"user_code": "ZZZZ-ZZZZ-ZZZZ"}, auth())
        assert response.status_code == 400
    assert approve(client, request, auth()).status_code == 429


def capture_form():
    image = io.BytesIO()
    Image.new("RGB", (640, 360), "green").save(image, format="PNG")
    return {"discovery_json": json.dumps({"DT": "Mineral", "UA": "0x1234", "AccountId": "private"}),
            "save_name": "Test save", "platform": "Steam", "client_version": "0.3.8-alpha",
            "permission_confirmed": "true", "public_attribution": "true", "contributor": "forged-name"}, image.getvalue()


def test_capture_submission_binds_profile_name_privacy_and_stays_pending(passport):
    client, engine, _, _ = passport
    _, result = connect(passport)
    form, image = capture_form()
    response = client.post("/captures", headers={"Authorization": "Bearer " + result["access_token"],
                                               "X-Admin-Actor": "forged-admin", "X-Admin-Key": "ignored"},
                           data=form, files={"image": ("test.png", image, "image/png")})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "pending_review"
    with Session(engine) as session:
        row = session.scalar(select(CaptureSubmission))
        assert row.contributor == "Name tester" and row.contributor_profile_id == "tester"
        assert row.public_attribution is False and row.status == "pending"
        assert "AccountId" not in row.discovery_record
        assert row.published_discovery_id is None


def test_legacy_rollout_and_invalid_bearer_never_falls_back(passport):
    client, _, _, _ = passport
    form, image = capture_form()
    headers = {"X-Admin-Actor": "Visceral", "X-Admin-Key": "legacy-test-only"}
    response = client.post("/captures", headers={**headers, "Authorization": "Bearer invalid"},
                           data=form, files={"image": ("test.png", image, "image/png")})
    assert response.status_code == 401
    form["permission_confirmed"] = "false"
    assert client.post("/captures", headers=headers, data=form,
                       files={"image": ("test.png", image, "image/png")}).status_code == 400
    form["permission_confirmed"] = "true"
    response = client.post("/captures", headers=headers, data=form,
                           files={"image": ("test.png", image, "image/png")})
    assert response.status_code == 200, response.text
    assert response.json()["contributor"] == "Visceral"


@pytest.mark.skipif(not os.environ.get("CAPTURE_AUTH_TEST_DATABASE_URL"), reason="Requires concurrent PostgreSQL transactions")
def test_two_concurrent_exchanges_issue_exactly_one_token(passport):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    client, _, auth, _ = passport
    request = start(client)
    assert approve(client, request, auth()).status_code == 200
    barrier = Barrier(2)
    def run():
        barrier.wait(timeout=5)
        return exchange(client, request)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert sorted(response.status_code for response in results) == [200, 400]
    assert sum(response.json().get("status") == "authorized" for response in results) == 1
