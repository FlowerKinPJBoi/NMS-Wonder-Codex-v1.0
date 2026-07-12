# Deploy Wonder Codex v1.4.2

Upload this hotfix into the repository root while preserving folders. Replace the existing files and commit to `main`.

Files included:

- `import.html`
- `importer.js`
- `importer.css`
- `api/app/config.py`
- `api/app/routers/submissions.py`
- `CHANGELOG_v1.4.2.md`

No database migration or environment-variable change is required.

After the Static Site and Web Service deploy:

1. Confirm `/api/health` reports version `1.4.2`.
2. Hard-refresh `/import.html` with `Ctrl + Shift + R`.
3. Select a Steam/GOG folder. Cache files should appear only under “auxiliary cache files ignored”; `.hg` files should appear under “Raw Steam/GOG slots detected” and should not be clickable.
4. A cache file chosen manually should be blocked from submission if it produces zero Wonder records.
