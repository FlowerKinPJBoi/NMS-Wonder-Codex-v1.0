# Wonder Codex deployment

Deploy the same `main` revision to both DigitalOcean App Platform components.

## Static Site

- Source directory: repository root
- Public domain: `https://wondercodex.com`
- No build step is required.

## API Web Service

- Source directory: `/api`
- Route: `/api`
- HTTP port: `8080`
- Dockerfile: `api/Dockerfile`

Production configuration belongs in encrypted DigitalOcean environment
variables. Never commit real values. The service currently recognizes:

- `DATABASE_URL`
- `ALLOWED_ORIGINS`
- `RUN_MIGRATIONS_ON_START`
- `IP_HASH_SALT`
- `MAX_REQUESTS_PER_HOUR`
- `ADMIN_API_KEY_PJ` and `ADMIN_API_KEY_BOOTS`
- `ADMIN_API_KEYS` as an optional JSON-object alternative
- `SPACES_ACCESS_KEY`, `SPACES_SECRET_KEY`, `SPACES_REGION`,
  `SPACES_BUCKET`, `SPACES_ENDPOINT`, and `SPACES_CDN_URL`

Use independent random administrator keys. Keep the legacy `ADMIN_API_KEY`
only while migrating an older client, then remove it from the service
environment.

## Deployment checks

After both components are healthy:

1. Open `https://wondercodex.com/api/health`.
2. Open `https://wondercodex.com/` and hard-refresh with `Ctrl+Shift+R`.
3. Confirm the catalog and an individual record load.
4. Confirm `https://wondercodex.com/map.html` loads Galaxy 1 — Euclid.
5. Confirm the admin review console accepts a named PJ or Boots credential.
6. Confirm `/admin/apps/` reports private storage online before uploading a
   reviewed inner application ZIP.

The v1.10.0 deployment requires no new migration or environment variable.
