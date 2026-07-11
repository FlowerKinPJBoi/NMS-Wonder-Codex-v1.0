# Deploy Wonder Codex v1.3.3

1. Upload the package contents to the repository root, preserving folders.
2. Replace the listed existing files.
3. Commit to `main`.
4. Allow both the Static Site and Web Service to redeploy.
5. Confirm `/api/health` reports version `1.3.3`, database ready, and image storage configured.
6. Open `record.html?id=3849&hotfix=133` and press Ctrl+Shift+R once.

The already-approved image does not need to be uploaded or approved again.

## Why this works

The API confirms that the image record is approved and then redirects the browser to a one-hour signed Spaces URL. The same signed-link mechanism already used for private Admin previews is therefore used for public approved-image delivery.

No database migration, Spaces setting change, or environment-variable change is required.
