# Wonder Codex v1.8.3 — Private App Vault

## Added

- New authenticated static route: `/admin/apps/`.
- Reuses the existing named PJ and Boots administrator credentials stored in browser `sessionStorage` for the current tab only.
- Separate release cards for:
  - Wonder Codex Importer `0.2.0-beta` (read-only trusted-tester app);
  - Pegasus Transit Admin `0.3.0-alpha` (restricted save-writing operator app).
- Admin-only build installation through the API.
- Server-side ZIP validation requires the correct executable inside each release, rejects corrupt/truncated archives, rejects unsafe paths and encrypted ZIPs, verifies CRCs, and calculates SHA-256.
- Private DigitalOcean Spaces objects with ten-minute presigned download links.
- Version, filename, size, upload operator, upload time, and SHA-256 display in the vault.

## Security boundaries

- No application ZIP is placed in the public static site.
- Knowing or guessing `/admin/apps/` does not grant access to release metadata, uploads, or downloads.
- Permanent Spaces URLs are not exposed. The API issues a short-lived URL only after named administrator authentication.
- Importer and Pegasus artifacts use different fixed storage keys and expected executable checks.
- The vault does not weaken the Importer's read-only contract or make Pegasus Transit public.

## Deployment

See `DEPLOY_PRIVATE_APPS_v1.8.3.md`.
