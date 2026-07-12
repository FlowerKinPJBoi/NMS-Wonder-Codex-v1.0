# Deploy Wonder Codex v1.4

## 1. Safety check

Confirm the DigitalOcean managed PostgreSQL **Restore from backup** option is available before deploying.

## 2. Upload to GitHub

Upload the contents of this package to the root of the Wonder Codex GitHub repository. Replace the existing website files and the entire `api` folder while preserving the folder structure.

Commit the changes to `main`.

## 3. DigitalOcean deployment

Allow both components to redeploy:

- Static Site route: `/`
- Web Service route: `/api`

Keep the current environment variables unchanged. No new variable is required.

The Web Service still needs:

- `DATABASE_URL`
- `ALLOWED_ORIGINS`
- `ADMIN_API_KEY`
- `IP_HASH_SALT`
- `MAX_REQUESTS_PER_HOUR`
- `RUN_MIGRATIONS_ON_START=true`
- all six existing `SPACES_*` variables

## 4. Migration

Runtime Logs should show:

```text
Database migrations completed.
```

Migration `0004_private_attribution` adds Boolean privacy fields only. It does not delete or rewrite existing discoveries, images, or verification records.

## 5. Health check

Open:

```text
https://wondercodex.com/api/health
```

Expected:

```text
version: 1.4.0
database.ready: true
image_storage.configured: true
```

## 6. Browser refresh

Open the pages below and press `Ctrl + Shift + R` once:

```text
https://wondercodex.com/import.html
https://wondercodex.com/contribute.html
https://wondercodex.com/admin.html
https://wondercodex.com/database.html
```

## 7. Private-attribution test

1. Submit a small save with **Keep my contributor name private** checked.
2. Open Admin → Data and confirm the real contributor name appears with a privacy indicator.
3. Approve the batch.
4. Open a resulting public record.
5. Confirm it displays `Anonymous Contributor`, does not expose the save name, and cannot be found by searching the private contributor name.

Repeat with one image or location verification when convenient.

## 8. Save Finder alpha test

1. Open `import.html`.
2. Click **Allow & choose Steam/GOG folder**.
3. Select a copied or active NMS save folder read-only.
4. Confirm decoded JSON files appear under **Ready to analyze**.
5. Confirm raw `.hg` files appear under **Raw Steam/GOG slots detected**.
6. Select a decoded JSON entry and run the existing analyzer.
7. Download the local scan manifest if raw slot research is needed.

The manifest contains only filenames, paths, sizes, dates, and classification flags. It does not contain save-file contents.
