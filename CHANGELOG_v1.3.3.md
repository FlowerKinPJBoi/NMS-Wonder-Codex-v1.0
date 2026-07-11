# Wonder Codex v1.3.3 — Approved Image Delivery Hotfix

## Fixed

- Approved images now redirect to a fresh, short-lived signed DigitalOcean Spaces URL.
- Public image access remains gated by the approved database status.
- The browser no longer depends on CDN/object ACL propagation or API byte streaming.
- Record-page image requests are cache-busted for this release.
- Includes the v1.3.2 large community submission fixes.

No database migration or new environment variable is required.
