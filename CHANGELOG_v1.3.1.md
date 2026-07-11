# Wonder Codex v1.3.1

## Approved image delivery hotfix

- Adds a same-origin approved-image delivery endpoint at `/api/images/{image_id}/content`.
- Reads approved objects from the private Spaces bucket using the Web Service credentials.
- Keeps pending images private and inaccessible through the public endpoint.
- Uses immutable browser caching and ETags for approved image IDs.
- Public catalog and record APIs now return the reliable same-origin image URL.
- Existing approved images begin working automatically; no re-upload or re-approval is required.
- Retains the direct CDN URL in API metadata for later diagnostics.
- No database migration is required.
