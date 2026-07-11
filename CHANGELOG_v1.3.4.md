# Wonder Codex v1.3.4 — Private Image Byte Delivery

## Fixed

- Approved images are now returned as normal image bytes by the Wonder Codex API.
- Removed the browser redirect to a signed Spaces URL.
- Removed dependence on public object ACLs and CDN propagation for catalog display.
- Added fallback lookup for the stored key, canonical approved key, and original pending key.
- Automatically repairs an old database object key when a fallback file is found.
- Public record pages report `Image available` whenever an approved image exists.

## Changed

New image approvals remain private in Spaces. The database approval status is the public access gate.

No migration or environment-variable change is required.
