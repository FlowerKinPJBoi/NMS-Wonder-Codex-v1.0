from __future__ import annotations

import hashlib
import logging
import re

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from ..config import get_settings
from .daedalus_builder import safe_build_filename


logger = logging.getLogger(__name__)


def _client():
    settings = get_settings()
    if not settings.spaces_private_ready:
        raise HTTPException(status_code=503, detail="Private Daedalus build storage is not configured yet.")
    return boto3.client(
        "s3",
        region_name=settings.spaces_region,
        endpoint_url=settings.spaces_endpoint,
        aws_access_key_id=settings.spaces_access_key,
        aws_secret_access_key=settings.spaces_secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def store_build_artifact(object_key: str, body: bytes, filename: str, actor: str) -> tuple[str, int]:
    settings = get_settings()
    digest = hashlib.sha256(body).hexdigest()
    safe_name = safe_build_filename(filename)
    try:
        _client().put_object(
            Bucket=settings.spaces_bucket,
            Key=object_key,
            Body=body,
            ACL="private",
            ContentType="application/octet-stream",
            CacheControl="private, no-store",
            ContentDisposition=f'attachment; filename="{safe_name}"',
            Metadata={
                "sha256": digest,
                "actor": re.sub(r"[^A-Za-z0-9._+-]+", "-", actor)[:80],
            },
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Could not store Daedalus build artifact %s", object_key)
        raise HTTPException(status_code=502, detail="Private storage did not accept the generated Daedalus build.") from exc
    return digest, len(body)


def read_build_artifact(object_key: str, *, maximum_bytes: int, expected_sha256: str = "", expected_size: int = 0) -> bytes:
    settings = get_settings()
    try:
        response = _client().get_object(Bucket=settings.spaces_bucket, Key=object_key)
        stream = response["Body"]
        try:
            body = stream.read(maximum_bytes + 1)
        finally:
            stream.close()
    except (BotoCoreError, ClientError, KeyError) as exc:
        logger.exception("Could not read Daedalus build artifact %s", object_key)
        raise HTTPException(status_code=502, detail="The stored Daedalus build could not be read.") from exc
    if len(body) > maximum_bytes:
        raise HTTPException(status_code=413, detail="The stored Daedalus build exceeds the configured limit.")
    if expected_size and len(body) != expected_size:
        raise HTTPException(status_code=409, detail="The stored Daedalus build no longer matches its recorded size.")
    digest = hashlib.sha256(body).hexdigest()
    if expected_sha256 and digest.casefold() != expected_sha256.casefold():
        raise HTTPException(status_code=409, detail="The stored Daedalus build no longer matches its recorded digest.")
    return body


def signed_build_url(object_key: str, filename: str) -> str:
    settings = get_settings()
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.spaces_bucket,
                "Key": object_key,
                "ResponseContentType": "application/octet-stream",
                "ResponseContentDisposition": f'attachment; filename="{safe_build_filename(filename)}"',
            },
            ExpiresIn=settings.daedalus_download_seconds,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Could not sign Daedalus build download %s", object_key)
        raise HTTPException(status_code=502, detail="Could not create a private Daedalus build download.") from exc
