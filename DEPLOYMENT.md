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
- `ANALYTICS_ENABLED`, `ANALYTICS_OWNER_ACTOR`,
  `ANALYTICS_RETENTION_DAYS`, and `ANALYTICS_MAX_EVENTS_PER_MINUTE`
- `ADMIN_API_KEY_PJ` and `ADMIN_API_KEY_BOOTS`
- `ADMIN_API_KEYS` as an optional JSON-object alternative
- `TESTER_API_KEY_MENOMOO`, `TESTER_API_KEY_FLOPPYDONKEY`,
  `TESTER_API_KEY_DARKBELLATOR`, `TESTER_API_KEY_OLGRAVYLEG`,
  `TESTER_API_KEY_MONKETSU`, and `TESTER_API_KEY_READYFIREAIM`
- `SPACES_ACCESS_KEY`, `SPACES_SECRET_KEY`, `SPACES_REGION`,
  `SPACES_BUCKET`, `SPACES_ENDPOINT`, and `SPACES_CDN_URL`

Use independent random administrator keys. Keep the legacy `ADMIN_API_KEY`
only while migrating an older client, then remove it from the service
environment.

Restricted testers do not belong in `ADMIN_API_KEYS`. Add the six scalar
variables listed above as separate encrypted Runtime values on the API Web
Service. Use a different long random value for each person. Do not add the old
`TESTER_API_KEYS` JSON variable; DigitalOcean's editor may reject its braces.

Those keys can authorize Pegasus Transit and create private application
downloads. They cannot open the review console, approve catalog data, upload
replacement builds, or use other administrator routes. PJ and Boots remain in
`ADMIN_API_KEYS` with full administrator scope.

## Deployment checks

After both components are healthy:

1. Open `https://wondercodex.com/api/health`.
2. Open `https://wondercodex.com/` and hard-refresh with `Ctrl+Shift+R`.
3. Confirm the catalog and an individual record load.
4. Confirm `https://wondercodex.com/map.html` loads Galaxy 1 — Euclid.
5. Confirm the admin review console accepts a named PJ or Boots credential.
6. Confirm a restricted tester can unlock `/admin/apps/`, cannot see the review
   console or replacement-build controls, and can authorize Pegasus Transit.
7. Confirm `/admin/apps/` reports private storage online before uploading a
   reviewed inner application ZIP.
8. Browse two or three public pages, then confirm PJ can open
   `https://wondercodex.com/admin/analytics/` with the existing named PJ admin
   credential. Confirm a Boots or tester credential is refused there.

The v1.13.0 deployment adds analytics database migration `0006`. With
`RUN_MIGRATIONS_ON_START=true`, the API applies it automatically. No new
environment variable is required: analytics defaults to enabled, owner `PJ`,
90-day anonymous journey retention, and 120 events per minute per volatile
rate-limit key. Detailed activity expires; daily aggregate totals remain.
