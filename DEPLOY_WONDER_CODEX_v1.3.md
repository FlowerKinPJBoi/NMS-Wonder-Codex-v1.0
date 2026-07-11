# Wonder Codex v1.3 — Image System & Portal Glyph Keypad

## Before deployment

1. Confirm the DigitalOcean managed PostgreSQL restore option is available.
2. Confirm these variables are attached to the **Web Service**:

```text
SPACES_ACCESS_KEY       encrypted
SPACES_SECRET_KEY       encrypted
SPACES_REGION           nyc3
SPACES_BUCKET           wondercodex-media
SPACES_ENDPOINT         https://nyc3.digitaloceanspaces.com
SPACES_CDN_URL          https://wondercodex-media.nyc3.cdn.digitaloceanspaces.com
RUN_MIGRATIONS_ON_START true
```

## Deploy

Upload this package into the GitHub repository root, replacing the existing files and `api` folder. Commit to `main`. DigitalOcean should redeploy both the Static Site and Web Service.

Migration `0003_image_contributions` adds one table and indexes. It does not delete existing discoveries, submissions, verifications, or audit events.

## Verify

1. Runtime Logs contain `Database migrations completed.`
2. `https://wondercodex.com/api/health` reports version `1.3.0`, database ready, and `image_storage.configured: true`.
3. Open `contribute.html?mode=verify` and confirm the 16 clickable glyph buttons fill the twelve-slot address.
4. Open `contribute.html?mode=image`, select a record, upload a test screenshot, confirm permission, and submit.
5. Open `admin.html` → **Images**, review the private preview, and approve as primary.
6. Open the public record and catalog; the approved image should be served through the Spaces CDN.

## Storage behavior

- Incoming images are validated, orientation-corrected, metadata-stripped, and encoded as WebP.
- Pending objects are private and shown to admins with a short-lived signed URL.
- Approved objects move to `approved/<discovery_id>/...`, become public-read, and use the CDN URL.
- Rejected pending objects are deleted.
- Maximum upload size: 15 MB.
- Minimum dimensions: 640×360.

## Rollback

Revert the GitHub commit to restore the previous application version. The additive image table can remain safely in PostgreSQL. Do not run the Alembic downgrade while approved media is in use.
