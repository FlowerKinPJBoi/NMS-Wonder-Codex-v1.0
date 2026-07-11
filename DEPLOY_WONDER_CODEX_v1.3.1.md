# Deploy Wonder Codex v1.3.1

This is a delivery-path hotfix for approved images. It does not change the database schema.

1. Upload the package contents to the repository root, replacing the existing files and `api` folder.
2. Commit to `main`.
3. Let DigitalOcean redeploy the Static Site and Web Service.
4. Confirm `/api/health` reports version `1.3.1` and image storage configured.
5. Open `record.html?id=3849` with a hard refresh.

The already-approved image for WC-M-003849 should display automatically. Do not re-upload it.
