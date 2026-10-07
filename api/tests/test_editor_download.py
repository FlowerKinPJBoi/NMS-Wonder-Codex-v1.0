from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.routers import downloads


@pytest.fixture
def download(monkeypatch):
    settings = SimpleNamespace(editor_download_approved=False)
    metadata = {
        "sha256": downloads.EDITOR_SHA256,
        "size_bytes": downloads.EDITOR_SIZE_BYTES,
        "version": downloads.EDITOR_RELEASE.suggested_version,
    }
    inspect = Mock(return_value=metadata)
    sign = Mock(return_value="https://storage.example.invalid/editor.zip?signature=test")
    monkeypatch.setattr(downloads, "get_settings", lambda: settings)
    monkeypatch.setattr(downloads, "release_status", inspect)
    monkeypatch.setattr(downloads, "signed_release_url", sign)
    client = TestClient(app, follow_redirects=False)
    yield client, settings, inspect, sign
    client.close()


def test_download_is_closed_by_default(monkeypatch):
    monkeypatch.delenv("EDITOR_DOWNLOAD_APPROVED", raising=False)
    assert Settings(_env_file=None).editor_download_approved is False


def test_unapproved_download_never_reads_or_signs_storage(download):
    client, _, inspect, sign = download
    response = client.get("/api/downloads/editor")
    assert response.status_code == 503
    assert "not available yet" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "location" not in response.headers
    inspect.assert_not_called()
    sign.assert_not_called()


@pytest.mark.parametrize("change", [
    None,
    {"sha256": "0" * 64},
    {"size_bytes": downloads.EDITOR_SIZE_BYTES - 1},
    {"version": "1.0.1"},
])
def test_missing_or_different_package_cannot_be_downloaded(download, change):
    client, settings, inspect, sign = download
    settings.editor_download_approved = True
    inspect.return_value = None if change is None else {**inspect.return_value, **change}
    response = client.get("/api/downloads/editor")
    assert response.status_code == 503
    assert "temporarily unavailable" in response.text
    assert "location" not in response.headers
    sign.assert_not_called()


@pytest.mark.parametrize("failing_step", ["inspect", "sign"])
def test_storage_failure_shows_a_retry_message_without_internal_details(download, failing_step):
    client, settings, inspect, sign = download
    settings.editor_download_approved = True
    target = inspect if failing_step == "inspect" else sign
    target.side_effect = HTTPException(status_code=502, detail="internal storage detail")
    response = client.get("/api/downloads/editor")
    assert response.status_code == 503
    assert "temporarily unavailable" in response.text
    assert "internal storage detail" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_approved_download_redirects_only_to_the_pinned_editor_archive(download):
    client, settings, inspect, sign = download
    settings.editor_download_approved = True
    response = client.get("/api/downloads/editor?key=admin-apps/pegasus-transit/current.zip")
    assert response.status_code == 303
    assert response.headers["location"] == sign.return_value
    assert response.headers["cache-control"] == "no-store"
    inspect.assert_called_once_with(downloads.EDITOR_RELEASE)
    sign.assert_called_once_with(downloads.EDITOR_RELEASE, downloads.EDITOR_FILENAME)
