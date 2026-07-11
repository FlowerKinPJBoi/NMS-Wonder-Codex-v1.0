from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import get_settings

logger = logging.getLogger(__name__)
Image.MAX_IMAGE_PIXELS = 80_000_000


@dataclass(frozen=True)
class PreparedImage:
    body: bytes
    content_type: str
    width: int
    height: int
    original_filename: str


def _client():
    settings = get_settings()
    if not settings.spaces_ready:
        raise HTTPException(status_code=503, detail="Image storage is not configured yet.")
    return boto3.client(
        "s3",
        region_name=settings.spaces_region,
        endpoint_url=settings.spaces_endpoint,
        aws_access_key_id=settings.spaces_access_key,
        aws_secret_access_key=settings.spaces_secret_key,
        config=Config(signature_version="s3v4"),
    )


async def prepare_upload(upload: UploadFile) -> PreparedImage:
    settings = get_settings()
    raw = await upload.read(settings.max_image_bytes + 1)
    if len(raw) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail=f"Image exceeds the {settings.max_image_mb} MB upload limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    try:
        with Image.open(io.BytesIO(raw)) as source:
            source.verify()
        with Image.open(io.BytesIO(raw)) as source:
            source = ImageOps.exif_transpose(source)
            width, height = source.size
            if width < settings.min_image_width or height < settings.min_image_height:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image must be at least {settings.min_image_width}×{settings.min_image_height} pixels.",
                )
            if width > settings.max_image_dimension or height > settings.max_image_dimension:
                source.thumbnail((settings.max_image_dimension, settings.max_image_dimension), Image.Resampling.LANCZOS)
                width, height = source.size
            if source.mode not in {"RGB", "RGBA"}:
                source = source.convert("RGBA" if "transparency" in source.info else "RGB")
            output = io.BytesIO()
            source.save(output, "WEBP", quality=92, method=6)
            body = output.getvalue()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="The file is not a valid PNG, JPEG, or WebP image.") from exc

    return PreparedImage(
        body=body,
        content_type="image/webp",
        width=width,
        height=height,
        original_filename=(upload.filename or "screenshot")[:255],
    )


def put_pending(key: str, prepared: PreparedImage) -> None:
    settings = get_settings()
    try:
        _client().put_object(
            Bucket=settings.spaces_bucket,
            Key=key,
            Body=prepared.body,
            ACL="private",
            ContentType=prepared.content_type,
            CacheControl="private, no-store",
            Metadata={"original-filename": prepared.original_filename},
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Spaces upload failed")
        raise HTTPException(status_code=502, detail="Image storage did not accept the upload.") from exc


def signed_review_url(key: str, expires_seconds: int = 900) -> str:
    settings = get_settings()
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.spaces_bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Could not create signed review URL")
        raise HTTPException(status_code=502, detail="Could not create a temporary review link.") from exc


def publish_object(source_key: str, destination_key: str) -> str:
    settings = get_settings()
    client = _client()
    try:
        client.copy_object(
            Bucket=settings.spaces_bucket,
            Key=destination_key,
            CopySource={"Bucket": settings.spaces_bucket, "Key": source_key},
            ACL="public-read",
            ContentType="image/webp",
            CacheControl="public, max-age=31536000, immutable",
            MetadataDirective="REPLACE",
        )
        client.delete_object(Bucket=settings.spaces_bucket, Key=source_key)
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Could not publish Spaces object")
        raise HTTPException(status_code=502, detail="Could not publish the approved image.") from exc
    return f"{settings.spaces_cdn_url.rstrip('/')}/{destination_key}"


def delete_object(key: str) -> None:
    if not key:
        return
    settings = get_settings()
    try:
        _client().delete_object(Bucket=settings.spaces_bucket, Key=key)
    except (BotoCoreError, ClientError):
        logger.exception("Could not remove Spaces object %s", key)
