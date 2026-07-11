# Wonder Codex v1.1 — Home + Admin Review Console

This release adds two major pieces:

1. A fully redesigned public Wonder Codex home page with live PostgreSQL statistics.
2. A browser-based admin review console at `/admin.html`.

It also upgrades the API to v1.1.0 with:

- `GET /api/stats` for public live counts.
- `GET /api/admin/summary` for the admin dashboard.
- `GET /api/admin/audit` for review history.
- Richer submission details and counts.
- FastAPI proxy/root-path support so `/api/docs` loads correctly.

## Deploy from GitHub

Upload the contents of this package to the root of the existing repository:

`FlowerKinPJBoi/NMS-Wonder-Codex-v1.0`

Replace the existing files when GitHub asks. The important root files are:

- `index.html`
- `styles.css`
- `script.js`
- `import.html`
- `importer.css`
- `importer.js`
- `admin.html`
- `admin.css`
- `admin.js`

Replace the existing `api` folder with the `api` folder in this package.

Commit the changes to `main`. Both DigitalOcean components already use autodeploy:

- Static Site source: repository root
- Web Service source: `api`

No new App Platform component is required.

## Keep these DigitalOcean settings

### Web Service

- Source directory: `api`
- Run command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- HTTP port: `8080`
- Routing rule: `/api`

### Environment variables

- `DATABASE_URL`: current working PostgreSQL URI ending in `?sslmode=require`
- `ADMIN_API_KEY`: long private key, encrypted
- `IP_HASH_SALT`: long private value, encrypted
- `MAX_REQUESTS_PER_HOUR`: `5`
- `RUN_MIGRATIONS_ON_START`: `true`
- `ALLOWED_ORIGINS`: `["https://wondercodex.com","https://www.wondercodex.com"]`

This release does not add a database migration. The current schema remains valid.

## Test after deployment

1. `https://wondercodex.com/api/health/live`
2. `https://wondercodex.com/api/health`
3. `https://wondercodex.com/api/stats`
4. `https://wondercodex.com/api/docs`
5. `https://wondercodex.com/`
6. `https://wondercodex.com/admin.html`

Use `Ctrl + Shift + R` once after deployment to clear cached CSS and JavaScript.

## Admin console use

Open `https://wondercodex.com/admin.html`.

Enter:

- Reviewer name: for example `PJ`
- Admin API key: the exact value stored in DigitalOcean as `ADMIN_API_KEY`

The key is stored only in `sessionStorage`, so it is cleared when that browser tab/session closes or when **Lock console** is clicked.

The console supports:

- Pending, approved, and rejected queues
- Search by save or contributor
- Submission counts and metadata
- Discovery, pet-match, issue, and raw previews
- JSON export
- Approve and publish entire batches
- Reject entire batches
- Reviewer notes
- Audit history

The detail preview is capped at 500 rows per section for browser performance. Approval still processes the full stored batch.

## Security

- Do not put `ADMIN_API_KEY` in GitHub, HTML, or JavaScript.
- Do not share screenshots containing environment variable values.
- The admin page is `noindex`, but the API key remains the real protection.
- Every approval or rejection is recorded in `audit_events`.
