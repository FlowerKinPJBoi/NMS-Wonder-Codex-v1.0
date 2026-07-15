# Deploy the Wonder Codex Private App Vault

## 1. Deploy both components

Deploy this source to the same two DigitalOcean App Platform components already used by Wonder Codex:

- the **Static Site** receives `admin/apps/`, `admin.html`, and the other browser assets;
- the **Web Service** receives the updated `api/` application.

No database migration is required.

## 2. Keep the existing API secrets

The vault reuses both existing systems:

- named operator keys (`ADMIN_API_KEY_PJ` / `ADMIN_API_KEY_BOOTS`, or the working `ADMIN_API_KEYS` JSON object);
- private DigitalOcean Spaces credentials already used for Wonder Codex image storage.

No new secret is required when those Spaces variables are already configured. They belong on the API Web Service (or app-level if that is how the current working image storage is configured), never on the Static Site alone.

Optional API setting:

```text
MAX_ADMIN_APP_MB=160
```

## 3. Open the vault

Visit:

```text
https://wondercodex.com/admin/apps/
```

The existing review-console session in the same browser tab is recognized. Otherwise enter the named PJ or Boots credentials.

## 4. Install the two current builds

Download each successful GitHub Actions artifact, extract the outer Actions package, and upload the **inner build ZIP** that directly contains the executable.

### Importer

```text
Version: 0.2.0-beta
ZIP: WonderCodexImporter-v0.2.0-beta-internal-win-x64.zip
Required file inside: WonderCodexImporter.exe
```

### Pegasus Transit Admin

```text
Version: 0.3.0-alpha
ZIP: PegasusTransitAdmin-v0.3.0-alpha-win-x64.zip
Required file inside: WonderCodexPegasusTransitAdmin.exe
```

The upload is accepted only after the server confirms a complete ZIP, correct executable, valid member CRCs, safe paths, size limit, and SHA-256. Installing a newer reviewed build replaces the current file for that app.

## 5. Test PJ and Boots separately

For each named operator:

1. Unlock `/admin/apps/` with that operator's own key.
2. Confirm both app cards show **Available**.
3. Copy the displayed SHA-256.
4. Click **Create private download**.
5. Hash the downloaded ZIP in PowerShell:

```powershell
(Get-FileHash .\DownloadedBuild.zip -Algorithm SHA256).Hash.ToLowerInvariant()
```

6. Confirm it exactly matches the vault fingerprint.
7. Lock the vault when finished.

## 6. Distribution rule

Send Boots the `/admin/apps/` page address and her own operator credential through separate private channels. Do not attach the executable ZIP to Discord and do not share PJ's key.

The current builds are not yet signed. HTTPS delivery, named access, temporary URLs, and SHA-256 make private testing more controlled, but Windows code signing remains the next durable trust improvement.
