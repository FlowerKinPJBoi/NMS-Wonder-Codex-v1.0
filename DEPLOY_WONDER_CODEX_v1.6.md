# Deploy Wonder Codex v1.6

## Scope

This is a full website/API update based on v1.5. It adds confirmed UA-derived routes and Pegasus Transit branding.

## Database impact

**No migration is required.** Existing database rows are not modified. Galaxy, glyph, and route-source values are derived when records are serialized and also have a browser-side fallback.

## Deploy

1. Confirm the public repository is `FlowerKinPJBoi/NMS-Wonder-Codex-v1.0`.
2. Upload the contents of this package to the repository root, preserving the `api`, `assets`, and `research` folders.
3. Commit directly to `main` with:

   `Add confirmed UA routes and Pegasus Transit`

4. Allow DigitalOcean App Platform to redeploy both:
   - the static site at `/`
   - the API service at `/api`

## Verification

1. Open `/api/health/live`.
2. Open a public record with UA `0x208BFF11112111` or `0x00208BFF11112111`.
3. Confirm:
   - Galaxy 256 — Odyalutai
   - portal code `208B11112111`
   - twelve glyph images
   - Location derived badge
4. Open the Contributions page and select the same record under Location Verification.
5. Confirm the galaxy and glyph fields are prefilled.
6. Open Admin → Catalog and confirm the decoded route appears without marking the location verified.
7. Confirm verified records still retain their approved catalog route and Verified badge.

## Rollback

Revert the deployment commit. No database rollback is necessary.
