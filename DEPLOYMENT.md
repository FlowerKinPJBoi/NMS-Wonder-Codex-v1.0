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
  `TESTER_API_KEY_MONKETSU`, `TESTER_API_KEY_READYFIREAIM`, and
  `TESTER_API_KEY_VISCERAL`, and `TESTER_API_KEY_EKIMO`
- `SPACES_ACCESS_KEY`, `SPACES_SECRET_KEY`, `SPACES_REGION`,
  `SPACES_BUCKET`, `SPACES_ENDPOINT`, and `SPACES_CDN_URL`
- `AUTH_SUPABASE_URL` and the public `AUTH_SUPABASE_ANON_KEY`
- `AUTH_JWT_SECRET` only when the Supabase project still signs access tokens
  with HS256; asymmetric signing keys are discovered through the project's JWKS
- `PROFILE_ENCRYPTION_KEY`, a Fernet key generated once with
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Accounts remain safely disabled unless both Supabase values are present. Add
Wonder Codex's production and local account-page callback URLs to the Supabase
redirect allow list, and configure the Discord provider in Supabase before
enabling the values in production. Never rotate `PROFILE_ENCRYPTION_KEY`
without first re-encrypting any stored NMS friend codes.

Use independent random administrator keys. Keep the legacy `ADMIN_API_KEY`
only while migrating an older client, then remove it from the service
environment.

Restricted testers do not belong in `ADMIN_API_KEYS`. Add the eight scalar
variables listed above as separate encrypted Runtime values on the API Web
Service. Use a different long random value for each person. Do not add the old
`TESTER_API_KEYS` JSON variable; DigitalOcean's editor may reject its braces.

Those keys can authorize Pegasus Transit, create private application downloads,
and submit locally confirmed Capture Companion pairs for owner review. They
cannot open the review console, approve catalog data, upload replacement builds,
or use other administrator routes. PJ and Boots remain in `ADMIN_API_KEYS` with
full administrator scope.

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
9. Open `https://wondercodex.com/feedback.html`, move through all four steps,
   and submit one clearly labeled test response. Confirm the success panel appears.
10. Open `https://wondercodex.com/admin/feedback/` with PJ's named credential,
    confirm the test response and pricing summary appear, then download the CSV.
11. Authorize Capture Companion with a named tester credential, submit one
    clearly labeled confirmed test pair, then confirm it appears only in the
    **Capture pairs** lane of the owner review console.
12. Reject that test pair and confirm neither its discovery nor image appears in
    the public catalog.
13. Open `/account.html`, test Discord and email magic-link sign-in, save a
    contributor profile, and confirm `/contribute.html?mode=image` fills that
    contributor name and attribution preference.
14. In the admin console's **Users** lane, change the test account from Regular
    to Tester, refresh the account page, and confirm its tier updates. Return the
    test account to Regular afterward.
15. Open `/contribute.html?mode=image`, keep **New discovery** selected, submit
    a clearly labeled console screenshot without choosing a catalog record, and
    confirm a `NEW-XXXXXXXX` reference appears.
16. Approve it from the admin console's **New screenshots** lane, confirm a WC
    record and primary image are created together, then remove the test record
    through the normal review process if it should not remain public.

The v1.17.0 deployment adds private Capture Companion migration
`0008_capture_submissions`. With `RUN_MIGRATIONS_ON_START=true`, the API applies
it automatically. No new environment variable is required. Capture submissions
use the existing named tester/admin credentials and private object storage.

The account foundation adds migration `0009_user_accounts`. Existing named
administrator and tester keys remain active during the account migration.
Migration `0010_new_discovery_screenshots` adds the private non-PC intake queue.
