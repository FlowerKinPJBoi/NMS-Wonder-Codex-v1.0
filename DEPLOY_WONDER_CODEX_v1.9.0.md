# Deploy Wonder Codex v1.9.0 to DigitalOcean

Deploy the same repository revision to both existing components.

1. Push or upload this source to the repository/branch already watched by the Wonder Codex DigitalOcean app.
2. In DigitalOcean App Platform, open the `wonder-codex` app and choose **Actions → Force Rebuild and Deploy**.
3. Confirm both the Static Site and API Web Service deploy from the same commit.
4. Keep `RUN_MIGRATIONS_ON_START=true` on the API Web Service. The API will apply migration `0005_asset_catalog` during startup.
5. Do not add new secrets for this release. The existing named `ADMIN_API_KEYS`, database, and storage settings are reused.
6. After the deployment is healthy, hard-refresh `https://wondercodex.com/database.html` with Ctrl+Shift+R.
7. Open each new catalog lane. It should show its labeled placeholder even before any assets are published.
8. Open the admin review console, choose **Assets**, and import a v0.2.1-beta Pegasus asset manifest.
9. Confirm source roles before publishing. Do not publish records labeled `unknown`.

Rollback: deploy the previous site revision. The new tables may remain in the database; the older application does not use them.
