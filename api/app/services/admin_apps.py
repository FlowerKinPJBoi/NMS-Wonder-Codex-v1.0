from __future__ import annotations

import hashlib
import logging
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from ..config import get_settings

logger = logging.getLogger(__name__)
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,39}$")


@dataclass(frozen=True)
class AdminApplication:
    slug: str
    title: str
    channel: str
    platform: str
    summary: str
    safety_note: str
    expected_executable: str
    suggested_version: str
    object_key: str


APPLICATIONS = (
    AdminApplication(
        slug="importer-beta",
        title="Wonder Codex Importer",
        channel="Trusted-tester beta",
        platform="Windows x64",
        summary="Read-only local save analysis and privacy-safe WCCP contribution export.",
        safety_note="Public-test app: reads supported local save copies without modifying them.",
        expected_executable="WonderCodexImporter.exe",
        suggested_version="0.2.2-beta",
        object_key="admin-apps/importer-beta/current.zip",
    ),
    AdminApplication(
        slug="capture-companion",
        title="Wonder Codex Capture Companion",
        channel="Private capture alpha",
        platform="Windows x64",
        summary="Read-only local discovery and screenshot pairing for trusted PC testers.",
        safety_note=(
            "Private alpha: watches only the selected screenshot folder, never modifies saves, "
            "and never uploads automatically."
        ),
        expected_executable="WonderCodexCaptureCompanion.exe",
        suggested_version="0.1.1-alpha",
        object_key="admin-apps/capture-companion/current.zip",
    ),
    AdminApplication(
        slug="pegasus-transit",
        title="Pegasus Transit Admin",
        channel="Restricted operator alpha",
        platform="Windows x64",
        summary="Private PJ/Boots transit console for verified Wonder Codex routes.",
        safety_note="Admin-only save writer: always creates a recovery backup before a transit write.",
        expected_executable="WonderCodexPegasusTransitAdmin.exe",
        suggested_version="0.3.1-alpha",
        object_key="admin-apps/pegasus-transit/current.zip",
    ),
)


def application_for(slug: str) -> AdminApplication:
    for application in APPLICATIONS:
        if application.slug == slug:
            return application
    raise HTTPException(status_code=404, detail="Unknown private application.")


def public_application(application: AdminApplication) -> dict:
    payload = asdict(application)
    payload.pop("expected_executable", None)
    payload.pop("object_key", None)
    return payload


def validate_version(version: str) -> str:
    cleaned = version.strip()
    if not VERSION_PATTERN.fullmatch(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Version must use 1–40 letters, numbers, dots, plus signs, underscores, or hyphens.",
        )
    return cleaned


def safe_filename(filename: str, fallback: str) -> str:
    cleaned = PurePosixPath((filename or "").replace("\\", "/")).name
    cleaned = re.sub(r"[^A-Za-z0-9._+-]+", "-", cleaned).strip(".-")
    if not cleaned.lower().endswith(".zip"):
        cleaned = f"{cleaned or fallback}.zip"
    return cleaned[:180]


def inspect_release_archive(
    application: AdminApplication,
    file_object: BinaryIO,
    *,
    maximum_bytes: int,
) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    file_object.seek(0)
    while True:
        chunk = file_object.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > maximum_bytes:
            raise HTTPException(status_code=413, detail="Application ZIP exceeds the private upload limit.")
        digest.update(chunk)

    if not size:
        raise HTTPException(status_code=400, detail="The selected ZIP is empty.")

    file_object.seek(0)
    try:
        with zipfile.ZipFile(file_object) as archive:
            members = archive.infolist()
            if not members:
                raise HTTPException(status_code=400, detail="The selected ZIP contains no files.")
            for member in members:
                normalized = member.filename.replace("\\", "/")
                parts = PurePosixPath(normalized).parts
                if normalized.startswith("/") or ".." in parts:
                    raise HTTPException(status_code=400, detail="The selected ZIP contains an unsafe path.")
                if member.flag_bits & 0x1:
                    raise HTTPException(status_code=400, detail="Password-protected application ZIPs are not accepted.")
            executable_present = any(
                PurePosixPath(member.filename.replace("\\", "/")).name.casefold()
                == application.expected_executable.casefold()
                for member in members
            )
            if not executable_present:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"This does not look like the inner {application.title} build ZIP; "
                        f"the expected executable {application.expected_executable} was not found."
                    ),
                )
            corrupt_member = archive.testzip()
            if corrupt_member:
                raise HTTPException(status_code=400, detail=f"The ZIP is corrupt near {corrupt_member}.")
    except HTTPException:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise HTTPException(status_code=400, detail="The selected file is not a complete, readable ZIP archive.") from exc
    finally:
        file_object.seek(0)

    return size, digest.hexdigest()


def _client():
    settings = get_settings()
    if not settings.spaces_private_ready:
        raise HTTPException(status_code=503, detail="Private application storage is not configured yet.")
    return boto3.client(
        "s3",
        region_name=settings.spaces_region,
        endpoint_url=settings.spaces_endpoint,
        aws_access_key_id=settings.spaces_access_key,
        aws_secret_access_key=settings.spaces_secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def release_status(application: AdminApplication) -> dict | None:
    settings = get_settings()
    if not settings.spaces_private_ready:
        return None
    try:
        response = _client().head_object(Bucket=settings.spaces_bucket, Key=application.object_key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            return None
        logger.exception("Could not inspect private application %s", application.slug)
        raise HTTPException(status_code=502, detail="Could not inspect private application storage.") from exc
    except BotoCoreError as exc:
        logger.exception("Could not inspect private application %s", application.slug)
        raise HTTPException(status_code=502, detail="Could not inspect private application storage.") from exc

    metadata = response.get("Metadata") or {}
    modified = response.get("LastModified")
    return {
        "available": True,
        "version": metadata.get("version", ""),
        "filename": metadata.get("filename", f"{application.slug}.zip"),
        "sha256": metadata.get("sha256", ""),
        "uploaded_by": metadata.get("uploaded-by", ""),
        "uploaded_at": metadata.get("uploaded-at", modified.isoformat() if modified else ""),
        "size_bytes": int(response.get("ContentLength") or 0),
    }


def store_release(
    application: AdminApplication,
    file_object: BinaryIO,
    *,
    version: str,
    filename: str,
    sha256: str,
    actor: str,
) -> None:
    settings = get_settings()
    uploaded_at = datetime.now(timezone.utc).isoformat()
    safe_actor = re.sub(r"[^A-Za-z0-9._+-]+", "-", actor).strip("-")[:80] or "admin"
    try:
        file_object.seek(0)
        _client().upload_fileobj(
            file_object,
            settings.spaces_bucket,
            application.object_key,
            ExtraArgs={
                "ACL": "private",
                "ContentType": "application/zip",
                "CacheControl": "private, no-store",
                "ContentDisposition": f'attachment; filename="{filename}"',
                "Metadata": {
                    "version": version,
                    "filename": filename,
                    "sha256": sha256,
                    "uploaded-by": safe_actor,
                    "uploaded-at": uploaded_at,
                },
            },
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Could not upload private application %s", application.slug)
        raise HTTPException(status_code=502, detail="Private application storage did not accept the upload.") from exc
    finally:
        file_object.seek(0)


def signed_release_url(application: AdminApplication, filename: str) -> str:
    settings = get_settings()
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.spaces_bucket,
                "Key": application.object_key,
                "ResponseContentType": "application/zip",
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=settings.admin_app_download_seconds,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Could not sign private application download %s", application.slug)
        raise HTTPException(status_code=502, detail="Could not create a temporary private download.") from exc
