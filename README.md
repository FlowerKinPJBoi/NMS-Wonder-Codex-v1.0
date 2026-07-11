# Wonder Codex v1.2 — Contributions, Catalog & Verification

This release expands the live Wonder Codex platform from save imports and batch review into a public catalog and location-verification workflow.

## Live features in this package

- Public searchable Wonder Database (`database.html`)
- Individual record pages (`record.html?id=...`)
- Derived stable WC IDs such as `WC-A-000123`
- Galaxy and 12-glyph portal display using PJ's supplied glyph artwork
- Contributions Hub (`contribute.html`)
- Working location-verification submissions
- Admin Verifications queue with approve/reject actions
- Admin Catalog editor for names, galaxy, glyphs, statuses, and notes
- WARP button position reserved and clearly disabled during research
- Wonder Save Finder added to the roadmap
- Image contribution form, screenshot guide, local preview, and record linking prepared for the next DigitalOcean Spaces step

## Image upload status

The browser-side image contribution workflow is prepared, but actual image submission remains disabled until DigitalOcean Spaces is connected. No screenshot is sent anywhere in v1.2.

## Database migration

`0002_catalog_verifications.py` adds non-destructive catalog fields to `discoveries` and creates `location_verifications`.

Keep `RUN_MIGRATIONS_ON_START=true` so Alembic applies the migration automatically during deployment.

See `DEPLOY_WONDER_CODEX_v1.2.md` for deployment and verification steps.
