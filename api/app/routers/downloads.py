"""Public download for the pinned Editor release, enabled through runtime configuration."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import get_settings
from ..services.admin_apps import AdminApplication, release_status, signed_release_url

router = APIRouter(prefix="/downloads", tags=["downloads"])

# Pin the exact release archive. It stays outside the public Git repository.
EDITOR_FILENAME = "Wonder-Codex-Editor-v1.0.0-Direct-UI-Windows-Setup.zip"
EDITOR_SHA256 = "26e3873c725f9510fcc51652835c33560a5b71efc1ad047722520e7b407aace9"
EDITOR_SIZE_BYTES = 132_334_940
EDITOR_RELEASE = AdminApplication(
    slug="wonder-codex-editor",
    title="Wonder Codex Editor",
    channel="Public release",
    platform="Windows 10/11 x64",
    summary="Wonder Codex Editor 1.0.0, Direct UI edition.",
    safety_note="TAZmd's separate Optimizer remains creator-owned and separately downloaded.",
    expected_executable="WonderCodexEditor.jar",
    suggested_version="1.0.0",
    object_key=f"editor-releases/{EDITOR_SHA256}/{EDITOR_FILENAME}",
)
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def unavailable(message: str) -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Wonder Codex Editor download</title></head><body><main>'
        f'<h1>Wonder Codex Editor</h1><p>{message}</p>'
        '<p><a href="/">Return to Wonder Codex</a></p>'
        '</main></body></html>',
        status_code=503,
        headers={**NO_STORE, "Retry-After": "3600"},
    )


@router.get("/editor", response_class=RedirectResponse)
def download_editor():
    if not get_settings().editor_download_approved:
        return unavailable("The Editor download is not available yet.")

    try:
        release = release_status(EDITOR_RELEASE)
        if (
            not release
            or release.get("sha256") != EDITOR_SHA256
            or release.get("size_bytes") != EDITOR_SIZE_BYTES
            or release.get("version") != EDITOR_RELEASE.suggested_version
        ):
            return unavailable("The Editor download is temporarily unavailable. Please try again later.")
        url = signed_release_url(EDITOR_RELEASE, EDITOR_FILENAME)
    except HTTPException:
        return unavailable("The Editor download is temporarily unavailable. Please try again later.")

    return RedirectResponse(url, status_code=303, headers=NO_STORE)
