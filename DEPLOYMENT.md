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
- `ERROR_RETENTION_DAYS` for the private operational diagnostic ledger (default `90`)
- `ADMIN_API_KEY_PJ` and `ADMIN_API_KEY_BOOTS`
- `ADMIN_API_KEYS` as an optional JSON-object alternative
- `TESTER_API_KEY_MENOMOO`, `TESTER_API_KEY_FLOPPYDONKEY`,
  `TESTER_API_KEY_DARKBELLATOR`, `TESTER_API_KEY_OLGRAVYLEG`,
  `TESTER_API_KEY_MONKETSU`, `TESTER_API_KEY_READYFIREAIM`,
  `TESTER_API_KEY_VISCERAL`, `TESTER_API_KEY_EKIMO`,
  `TESTER_API_KEY_JADEXP`, and `TESTER_API_KEY_KROSSKELT`
- `DAEDALUS_TRAINER_ACTORS` as a comma-separated named-operator allowlist
  (default `PJ,Boots,Krosskelt`)
- `DAEDALUS_REVIEWER_ACTORS` as a comma-separated review/release allowlist
  (default `PJ,Boots`)
- `MAX_DAEDALUS_PACKAGE_MB` and `DAEDALUS_DOWNLOAD_SECONDS` when the 40 MB /
  15 minute defaults need adjustment
- `OPENAI_API_KEY` as an encrypted API-service secret; never expose it to the
  static site or commit it to GitHub
- `DAEDALUS_MODEL` (default `gpt-5.6`), `DAEDALUS_REASONING_EFFORT` (default
  `medium`), and `DAEDALUS_GENERATION_TIMEOUT_SECONDS` (default `180`)
- `MAX_DAEDALUS_BUILD_MB`, `MAX_DAEDALUS_REFERENCE_MB`,
  `MAX_DAEDALUS_REFERENCES`, and `MAX_DAEDALUS_OPERATIONS` for the 40 MB build,
  8 MB/image, four-image, and 400-operation defaults
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

Restricted testers do not belong in `ADMIN_API_KEYS`. Add the scalar
variables listed above as separate encrypted Runtime values on the API Web
Service. Use a different long random value for each person. Do not add the old
`TESTER_API_KEYS` JSON variable; DigitalOcean's editor may reject its braces.

Those keys can authorize Pegasus Transit, create private application downloads,
and submit locally confirmed Capture Companion pairs for owner review. They
cannot open the review console, approve catalog data, upload replacement builds,
or use other administrator routes. PJ and Boots remain in `ADMIN_API_KEYS` with
full administrator scope.

Daedalus access is an additional allowlist, not a new administrator role. An
operator must still have an independent named admin/tester key. Trainers can
open the shared workspace, submit server-validated learning ZIPs, inspect the
queue, and download review packages. Reviewers can mark packages approved,
needs correction, or rejected. Only reviewers on the release allowlist can
perform the separate **release** transition that makes a record eligible for
production learning.

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
8. Open `/admin/apps/daedalus/` as Krosskelt (or another configured trainer).
   First, attach nothing and request `Build a sign that says "NMS 10 YEARS!"
   with a black backdrop and yellow lettering`; confirm Send is available and
   the workshop remains in its working state while the private job is queued,
   then Pass 1 returns a portable native prefab without a gateway 504. Then upload a small test NMSBASE,
   request one safe visible change, and confirm its Pass 1 download retains the
   source anchor exactly.
9. Request a second change in the same chat and confirm Pass 2 builds from Pass
   1 while Pass 1 remains downloadable. Mark the final result **Looks good**,
   submit it for learning review, and confirm it enters `pending_review`
   without becoming production-training eligible.
10. As PJ or Boots, mark the test package approved and confirm it is still not
   training eligible. Release it separately only if it is a genuine retained
   training record; otherwise reject it after the workflow test.
11. Browse two or three public pages, then confirm PJ can open
   `https://wondercodex.com/admin/analytics/` with the existing named PJ admin
   credential. Confirm a Boots or tester credential is refused there.
12. Open `https://wondercodex.com/feedback.html`, move through all four steps,
   and submit one clearly labeled test response. Confirm the success panel appears.
13. Open `https://wondercodex.com/admin/feedback/` with PJ's named credential,
    confirm the test response and pricing summary appear, then download the CSV.
14. Authorize Capture Companion with a named tester credential, submit one
    clearly labeled confirmed test pair, then confirm it appears only in the
    **Capture pairs** lane of the owner review console.
15. Reject that test pair and confirm neither its discovery nor image appears in
    the public catalog.
16. Open `/account.html`, test Discord and email magic-link sign-in, save a
    contributor profile, and confirm `/contribute.html?mode=image` fills that
    contributor name and attribution preference.
17. In the admin console's **Users** lane, change the test account from Regular
    to Tester, refresh the account page, and confirm its tier updates. Return the
    test account to Regular afterward.
18. Open `/contribute.html?mode=image`, keep **New discovery** selected, submit
    a clearly labeled console screenshot without choosing a catalog record, and
    confirm a `NEW-XXXXXXXX` reference appears.
19. Approve it from the admin console's **New screenshots** lane, confirm a WC
    record and primary image are created together, then remove the test record
    through the normal review process if it should not remain public.

The v1.17.0 deployment adds private Capture Companion migration
`0008_capture_submissions`. With `RUN_MIGRATIONS_ON_START=true`, the API applies
it automatically. No new environment variable is required. Capture submissions
use the existing named tester/admin credentials and private object storage.

The account foundation adds migration `0009_user_accounts`. Existing named
administrator and tester keys remain active during the account migration.
Migration `0010_new_discovery_screenshots` adds the private non-PC intake queue.
Migration `0011_daedalus_training_queue` adds the guarded Daedalus learning
queue. It reuses private Spaces storage and never treats client-side trust as a
production release decision.
Migration `0012_daedalus_corpus` adds released-lesson indexing and versioning.
Migration `0013_daedalus_builder_writer` adds private iterative build sessions
and immutable generated passes. With migrations enabled, both are applied by
the API service during deployment.
Migration `0014_operational_errors` adds PJ's private, sanitized operational
error ledger and Daedalus incident downloads. It is separate from anonymous
traffic analytics and defaults to 90-day retention.
Migration `0015_daedalus_build_jobs` adds durable private job state for OpenAI
background responses. Daedalus now acknowledges generation before the model
finishes and the browser polls the recorded job until the validated build file
is ready. No additional worker service or environment variable is required.
