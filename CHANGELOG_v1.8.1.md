# Wonder Codex v1.8.1 — Pegasus Transit operator bridge

- Added named administrator keys through `ADMIN_API_KEY_PJ` and `ADMIN_API_KEY_BOOTS` (with `ADMIN_API_KEYS` JSON also supported), while retaining the legacy single key during migration.
- Added `X-Admin-Actor` to protected API requests so PJ and Boots can use independent credentials.
- Added an administrator-only Pegasus Transit route download on travel-ready record pages.
- Added `.wctransit` route tickets containing WC ID, galaxy, glyphs, and redundant Universal Address validation data.
- Public visitors continue to see Pegasus Transit as restricted; route tickets do not contain credentials or private save data.
- Added deployment instructions for generating, configuring, rotating, and eventually retiring the legacy shared key.
