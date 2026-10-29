"""Private, verified FFC backups in the existing Wonder Codex Spaces bucket."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
import re
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .cloud_control import APPLICATION_ID, GUILD_ID, CHANNEL_ID
from .migration import export_snapshot
from .async_store import _completion_before_cancel

PREFIX = "ffc-wilds/backups/v1/"
KEEP_BACKUPS = 32
MAX_BACKUP_BYTES = 20 * 1024 * 1024
PRIVACY_PREFIX = PREFIX + "_privacy-checks/"
PRIVACY_CANARY = b"FFC Wilds private-storage check. This object contains no game or personal data.\n"


class BackupUnavailable(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def anonymous_status(url: str) -> int:
    """Read only the response status, without credentials, cookies or proxies."""
    request = Request(url, method="GET", headers={
        "User-Agent": "FFC-Wilds-Storage-Check/1", "Cache-Control": "no-cache", "Pragma": "no-cache"})
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            return response.status
    except HTTPError as response:
        try:
            return response.code
        finally:
            response.close()


class CloudBackups:
    def __init__(self, engine, store, *, environ=None, client=None, clock=time.time,
                 anonymous_read=None):
        self.engine, self.store = engine, store
        self.env = os.environ if environ is None else environ
        self.clock = clock
        self._client = client
        self._lock = asyncio.Lock()
        self._anonymous_read = anonymous_read or anonymous_status
        self._game_call = None

    def bind_client(self, client):
        """Share the host's one serialized game IO worker for save exports."""
        from .host_actions import game_call

        async def export_call(operation, *args, **kwargs):
            return await game_call(client, operation, *args, **kwargs)

        self._game_call = export_call

    def _settings(self):
        region = self.env.get("SPACES_REGION", "").strip()
        endpoint = self.env.get("SPACES_ENDPOINT", "").strip()
        bucket = self.env.get("SPACES_BUCKET", "").strip()
        parts = urlsplit(endpoint)
        if (not re.fullmatch(r"[a-z]+[0-9]+", region)
                or parts.scheme != "https" or parts.hostname != f"{region}.digitaloceanspaces.com"
                or parts.username or parts.password or parts.port not in (None, 443)
                or parts.path not in ("", "/") or parts.query or parts.fragment
                or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket)
                or not self.env.get("SPACES_ACCESS_KEY") or not self.env.get("SPACES_SECRET_KEY")):
            raise BackupUnavailable("Private cloud backup storage is not configured.")
        return region, endpoint, bucket

    def _storage(self):
        region, endpoint, bucket = self._settings()
        if self._client is None:
            import boto3
            from botocore.config import Config
            self._client = boto3.client("s3", region_name=region, endpoint_url=endpoint,
                aws_access_key_id=self.env["SPACES_ACCESS_KEY"],
                aws_secret_access_key=self.env["SPACES_SECRET_KEY"],
                config=Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2},
                              signature_version="s3v4"))
        return self._client, bucket

    def _privacy_check(self, client, bucket):
        region, _endpoint, configured_bucket = self._settings()
        if bucket != configured_bucket:
            raise BackupUnavailable("Private cloud backup storage could not be verified.")
        key = PRIVACY_PREFIX + uuid.uuid4().hex
        # Use the canonical origin URL, never a CDN, redirect or signed URL.
        url = f"https://{bucket}.{region}.digitaloceanspaces.com/{key}"
        try:
            client.put_object(Bucket=bucket, Key=key, Body=PRIVACY_CANARY,
                ACL="private", ContentType="text/plain", CacheControl="no-store",
                Metadata={"purpose": "private-storage-check"})
            head = client.head_object(Bucket=bucket, Key=key)
            if head.get("ContentLength") != len(PRIVACY_CANARY):
                raise BackupUnavailable("The private-storage check could not verify its test object.")
            stream = client.get_object(Bucket=bucket, Key=key)["Body"]
            try:
                received = stream.read(len(PRIVACY_CANARY) + 1)
            finally:
                stream.close()
            if received != PRIVACY_CANARY:
                raise BackupUnavailable("The private-storage check could not verify its test object.")
            status = self._anonymous_read(url)
            if type(status) is not int or status not in (401, 403, 404):
                raise BackupUnavailable("The storage privacy check did not deny public access. No game save was uploaded.")
        finally:
            # Even an uncertain PUT may have succeeded. Cleanup is restricted
            # to this single harmless object and must finish before a save PUT.
            try:
                client.delete_object(Bucket=bucket, Key=key)
            except Exception:
                raise BackupUnavailable("The private-storage check could not complete its cleanup. No game save was uploaded.") from None

    def check_privacy(self) -> dict:
        """Check configured storage without exporting or uploading game data."""
        try:
            client, bucket = self._storage()
            self._privacy_check(client, bucket)
            return {"status": "private", "checked_at": float(self.clock())}
        except BackupUnavailable:
            raise
        except Exception:
            raise BackupUnavailable("The cloud storage privacy check could not be completed. No game save was uploaded.") from None

    def _upload(self, snapshot):
        try:
            client, bucket = self._storage()
            # A bucket-wide public policy can override a private object ACL.
            # Probe harmless data before putting any part of the game save.
            self._privacy_check(client, bucket)
            created = float(self.clock())
            raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")
            if len(raw) > MAX_BACKUP_BYTES:
                raise BackupUnavailable("The save is too large for this backup format.")
            body = gzip.compress(raw, mtime=0)
            digest = hashlib.sha256(body).hexdigest()
            stamp = datetime.fromtimestamp(created, timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            name = f"wilds-{stamp}-{digest[:12]}.json.gz"
            key = PREFIX + name
            client.put_object(Bucket=bucket, Key=key, Body=body, ACL="private",
                ContentType="application/gzip", Metadata={"sha256": digest, "save-sha256": snapshot["sha256"]})
            head = client.head_object(Bucket=bucket, Key=key)
            if head.get("ContentLength") != len(body) or head.get("Metadata", {}).get("sha256") != digest:
                raise BackupUnavailable("The cloud backup verification did not match.")
            # Verify stored bytes, not merely the metadata submitted with them.
            response = client.get_object(Bucket=bucket, Key=key)
            stream = response["Body"]
            try:
                received = stream.read(len(body) + 1)
            finally:
                stream.close()
            if len(received) != len(body) or hashlib.sha256(received).hexdigest() != digest:
                raise BackupUnavailable("The saved backup could not be verified.")
            rows = []
            for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIX):
                for row in page.get("Contents", []):
                    # Retention is confined to files produced by this feature.
                    suffix = row["Key"][len(PREFIX):]
                    if re.fullmatch(r"wilds-[0-9]{8}T[0-9]{6}\.[0-9]{6}Z-[0-9a-f]{12}\.json\.gz", suffix):
                        rows.append(row)
            rows.sort(key=lambda row: row["Key"], reverse=True)
            for row in rows[KEEP_BACKUPS:]:
                client.delete_object(Bucket=bucket, Key=row["Key"])
            result = {"created_at": created, "sha256": digest, "size_bytes": len(body),
                      "name": name, "status": "verified", "retained_count": min(len(rows), KEEP_BACKUPS)}
            self.store.set_last_backup(result)
            return result
        except BackupUnavailable:
            raise
        except Exception:
            raise BackupUnavailable("The private cloud backup could not be verified. The database remains the primary save.") from None

    async def create(self):
        async with self._lock:
            options = {"application_id": APPLICATION_ID,
                       "expected_guild_id": GUILD_ID, "expected_channel_id": CHANNEL_ID}
            if self._game_call is not None:
                snapshot = await self._game_call(export_snapshot, self.engine, **options)
            else:
                # Standalone/local callers have no concurrently running host.
                # Export itself holds the engine transaction lock throughout.
                snapshot = export_snapshot(self.engine, **options)
            # Do not release this lock while a cancelled upload is still doing
            # verification, retention, or last-backup metadata writes.
            upload = asyncio.create_task(asyncio.to_thread(self._upload, snapshot))
            return await _completion_before_cancel(upload)
