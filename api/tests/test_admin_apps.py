from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import HTTPException

from app.routers import admin_apps as admin_apps_router
from app.config import Settings
from app.services.admin_apps import (
    APPLICATIONS,
    application_for,
    inspect_release_archive,
    safe_filename,
    validate_version,
)
from app.services.security import OperatorSession


def build_zip(filename: str, body: bytes = b"test executable") -> io.BytesIO:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, body)
        archive.writestr("SECURITY.md", "Private trusted-tester build")
    output.seek(0)
    return output


def test_private_app_registry_keeps_writer_separate_from_importer():
    assert [application.slug for application in APPLICATIONS] == [
        "importer-beta",
        "capture-companion",
        "pegasus-transit",
    ]
    assert application_for("importer-beta").expected_executable == "WonderCodexImporter.exe"
    assert application_for("capture-companion").expected_executable == "WonderCodexCaptureCompanion.exe"
    assert application_for("pegasus-transit").expected_executable == "WonderCodexPegasusTransitAdmin.exe"
    assert len({application.object_key for application in APPLICATIONS}) == len(APPLICATIONS)


def test_release_archive_is_hashed_and_expected_executable_is_required():
    application = application_for("importer-beta")
    archive = build_zip("publish/WonderCodexImporter.exe")
    size, digest = inspect_release_archive(application, archive, maximum_bytes=1_000_000)
    assert size > 0
    assert len(digest) == 64
    assert archive.tell() == 0


def test_capture_companion_release_requires_its_own_executable():
    application = application_for("capture-companion")
    archive = build_zip("publish/WonderCodexCaptureCompanion.exe")
    size, digest = inspect_release_archive(application, archive, maximum_bytes=1_000_000)
    assert size > 0
    assert len(digest) == 64

    with pytest.raises(HTTPException, match="expected executable"):
        inspect_release_archive(application, build_zip("WonderCodexImporter.exe"), maximum_bytes=1_000_000)


def test_wrong_or_incomplete_release_archive_is_rejected():
    application = application_for("pegasus-transit")
    with pytest.raises(HTTPException, match="expected executable"):
        inspect_release_archive(application, build_zip("WonderCodexImporter.exe"), maximum_bytes=1_000_000)

    truncated = build_zip(application.expected_executable)
    broken = io.BytesIO(truncated.getvalue()[:-18])
    with pytest.raises(HTTPException, match="complete, readable ZIP"):
        inspect_release_archive(application, broken, maximum_bytes=1_000_000)


def test_private_release_inputs_are_normalized():
    assert validate_version("0.3.1-alpha") == "0.3.1-alpha"
    assert validate_version("0.1.1-alpha") == "0.1.1-alpha"
    assert safe_filename("C:\\Downloads\\Pegasus Transit.zip", "pegasus") == "Pegasus-Transit.zip"
    with pytest.raises(HTTPException):
        validate_version("bad version with spaces")


def test_private_storage_does_not_require_a_public_cdn_url():
    settings = Settings(
        spaces_access_key="access",
        spaces_secret_key="secret",
        spaces_region="nyc3",
        spaces_bucket="wonder-codex",
        spaces_endpoint="https://nyc3.digitaloceanspaces.com",
        spaces_cdn_url="",
    )
    assert settings.spaces_private_ready is True
    assert settings.spaces_ready is False
    assert settings.max_admin_app_bytes == 160 * 1024 * 1024


def test_storage_status_failure_does_not_lock_operator_out(monkeypatch):
    def fail_status(_application):
        raise HTTPException(status_code=502, detail="Could not inspect private application storage.")

    monkeypatch.setattr(admin_apps_router, "release_status", fail_status)
    response = admin_apps_router.list_private_apps(
        operator=OperatorSession("PJ", frozenset({"admin", "apps:download", "apps:upload", "transit"}))
    )

    assert response["operator"] == "PJ"
    assert response["permissions"] == {"download": True, "upload": True, "transit": True}
    assert len(response["items"]) == 3
    assert all(item["release"] is None for item in response["items"])
    assert response["storage_warning"] == "Could not inspect private application storage."


def test_restricted_tester_can_open_vault_without_upload_authority(monkeypatch):
    monkeypatch.setattr(admin_apps_router, "release_status", lambda _application: None)
    response = admin_apps_router.list_private_apps(
        operator=OperatorSession("Menomoo", frozenset({"apps:download", "transit"}))
    )

    assert response["operator"] == "Menomoo"
    assert response["permissions"] == {"download": True, "upload": False, "transit": True}

def test_jadexp_and_krosskelt_have_independent_restricted_tester_keys():
    settings = Settings(
        tester_api_key_jadexp="jade-key",
        tester_api_key_krosskelt="kross-key",
    )

    assert settings.tester_api_keys["JadeXP"] == "jade-key"
    assert settings.tester_api_keys["Krosskelt"] == "kross-key"
    assert settings.tester_api_keys["JadeXP"] != settings.tester_api_keys["Krosskelt"]
