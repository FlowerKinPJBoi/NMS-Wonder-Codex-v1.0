from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..services.admin_apps import (
    APPLICATIONS,
    application_for,
    inspect_release_archive,
    public_application,
    release_status,
    safe_filename,
    signed_release_url,
    store_release,
    validate_version,
)
from ..services.security import require_admin_key

router = APIRouter(prefix="/admin/apps", tags=["admin-apps"])
logger = logging.getLogger(__name__)


@router.get("")
def list_private_apps(actor: str = Depends(require_admin_key)):
    settings = get_settings()
    items = []
    storage_warnings: list[str] = []
    for application in APPLICATIONS:
        item = public_application(application)
        try:
            item["release"] = release_status(application)
        except HTTPException as exc:
            # A release-status lookup must never lock an authorized operator out
            # of the vault. Upload and download operations still fail closed.
            item["release"] = None
            storage_warnings.append(str(exc.detail))
        except Exception as exc:
            logger.exception("Unexpected private storage status failure for %s", application.slug)
            item["release"] = None
            storage_warnings.append(
                f"Private storage status check failed ({type(exc).__name__})."
            )
        items.append(item)
    storage_warning = " ".join(dict.fromkeys(storage_warnings))
    return {
        "items": items,
        "operator": actor,
        "storage_ready": settings.spaces_private_ready,
        "storage_warning": storage_warning,
        "max_upload_bytes": settings.max_admin_app_bytes,
        "download_expires_seconds": settings.admin_app_download_seconds,
    }


@router.post("/{slug}/upload")
async def upload_private_app(
    slug: str,
    version: str = Form(...),
    archive: UploadFile = File(...),
    actor: str = Depends(require_admin_key),
):
    settings = get_settings()
    application = application_for(slug)
    cleaned_version = validate_version(version)
    filename = safe_filename(archive.filename or "", f"{slug}-{cleaned_version}")
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Private application releases must be ZIP files.")

    size, digest = await run_in_threadpool(
        inspect_release_archive,
        application,
        archive.file,
        maximum_bytes=settings.max_admin_app_bytes,
    )
    await run_in_threadpool(
        store_release,
        application,
        archive.file,
        version=cleaned_version,
        filename=filename,
        sha256=digest,
        actor=actor,
    )
    release = release_status(application) or {
        "available": True,
        "version": cleaned_version,
        "filename": filename,
        "sha256": digest,
        "uploaded_by": actor,
        "uploaded_at": "",
        "size_bytes": size,
    }
    return {"ok": True, "app": public_application(application), "release": release}


@router.post("/{slug}/download")
def create_private_download(slug: str, actor: str = Depends(require_admin_key)):
    settings = get_settings()
    application = application_for(slug)
    release = release_status(application)
    if not release:
        raise HTTPException(status_code=404, detail="No build has been installed for this application yet.")
    filename = safe_filename(release.get("filename", ""), application.slug)
    return {
        "download_url": signed_release_url(application, filename),
        "expires_seconds": settings.admin_app_download_seconds,
        "filename": filename,
        "sha256": release.get("sha256", ""),
        "requested_by": actor,
    }
