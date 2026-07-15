# Wonder Codex v1.8.5

- Keeps valid PJ and Boots operators signed into `/admin/apps/` when a DigitalOcean Spaces release-status lookup fails.
- Displays the private-storage warning inside the vault instead of returning a generic server error.
- Keeps release uploads and downloads fail-closed; this change does not weaken administrator authentication or storage protections.
- No database migration or new environment variable is required.
