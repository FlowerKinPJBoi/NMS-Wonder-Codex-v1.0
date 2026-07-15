# Deploy Wonder Codex Private Apps v1.8.4

Deploy the v1.8.4 source to both existing DigitalOcean components:

- **Static Site** for `/admin/apps/`, including `apps.js` and `testing.css`;
- **Web Service** for the private release API.

No database migration or new environment variable is required. Keep the existing named PJ/Boots administrator keys and private Spaces credentials on the API Web Service.

After deployment:

1. Hard-refresh `https://wondercodex.com/admin/apps/`.
2. Unlock with a named operator credential.
3. Confirm each app card has a collapsed **Testing brief**.
4. Open each brief and test both **Copy checklist** and **Download test report (.txt)**.
5. Confirm the Importer report contains no request for raw saves.
6. Confirm Pegasus displays separate Xbox and Steam lanes plus the failure stop rule.
7. Install the current reviewed inner build ZIPs if the vault still reports no build:
   - `WonderCodexImporter-v0.2.0-beta-internal-win-x64.zip`;
   - `PegasusTransitAdmin-v0.3.0-alpha-win-x64.zip`.

The full private-storage setup and SHA-256 verification procedure remains documented in `DEPLOY_PRIVATE_APPS_v1.8.3.md`.
