# Deploy Wonder Codex v1.2

## 1. Make a safety copy

Before a database migration, download a current database backup or confirm that your managed PostgreSQL backups are healthy. Migration `0002_catalog_verifications` only adds columns, indexes, and a new table; it does not delete existing Flower-Kin or PJ's Explorer records.

## 2. Replace the GitHub repository contents

Upload the complete contents of this package to the root of:

`FlowerKinPJBoi/NMS-Wonder-Codex-v1.0`

Replace existing files when GitHub asks. Keep the directory structure, especially:

- `api/`
- `assets/glyphs/`
- `database.html`
- `record.html`
- `contribute.html`
- `glyphs.js`
- `catalog.css`

Commit to `main`.

## 3. DigitalOcean configuration

No new environment variables are required for v1.2.

Keep the Web Service settings:

- Source Directory: `api`
- Run Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Route: `/api`

Keep these environment variables:

- `DATABASE_URL`
- `ALLOWED_ORIGINS`
- `ADMIN_API_KEY`
- `IP_HASH_SALT`
- `MAX_REQUESTS_PER_HOUR`
- `RUN_MIGRATIONS_ON_START=true`

`ALLOWED_ORIGINS` should remain a JSON array in DigitalOcean:

`["https://wondercodex.com","https://www.wondercodex.com"]`

## 4. Confirm the migration

Watch the Web Service deployment logs for:

`Database migrations completed.`

The API should report version `1.2.0`.

## 5. Test the public API

Open these routes:

- `https://wondercodex.com/api/health/live`
- `https://wondercodex.com/api/health`
- `https://wondercodex.com/api/stats`
- `https://wondercodex.com/api/discoveries?limit=3`
- `https://wondercodex.com/api/docs`

## 6. Test the website

Open:

- `https://wondercodex.com/`
- `https://wondercodex.com/database.html`
- `https://wondercodex.com/contribute.html`
- `https://wondercodex.com/import.html`
- `https://wondercodex.com/admin.html`

Use `Ctrl + Shift + R` once after the deployment.

## 7. Seed confirmed travel information

In `admin.html`:

1. Unlock the console.
2. Open **Catalog editor**.
3. Search for a published record.
4. Enter a display name, galaxy number/name, and the 12-character glyph code.
5. Set Location status to **Verified** only when both the galaxy number and all 12 glyphs are supported by evidence.
6. Save the record.

The public record page immediately displays the galaxy and PJ's portal glyph images.

## 8. Test a community verification

1. Open a record from `database.html`.
2. Click **Verify**.
3. Submit travel evidence from the Contributions Hub.
4. Open **Verifications** in `admin.html`.
5. Review and approve or reject it.
6. When approved with **Apply location** checked, a complete galaxy/glyph submission is applied to the catalog. The location becomes Verified only when the contributor marked both the system reached and the discovery present.

## Image storage next

The Images form deliberately does not upload yet. The next release will add DigitalOcean Spaces credentials, file validation, object keys, thumbnails, image metadata, and the live Admin Images queue.
