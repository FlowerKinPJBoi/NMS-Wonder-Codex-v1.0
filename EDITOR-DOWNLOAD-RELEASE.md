# Wonder Codex Editor 1.0.0 website download

PJ authorized the public Wonder Codex Editor v1 release on October 7, 2026.
The steps below publish its website download. Preparing or merging this source
does not upload the archive or enable the API download flag.

The homepage's Research and Roadmap navigation, sections, and links back to
those sections are removed. Public headers offer **Download Editor**, using
`/api/downloads/editor`. The existing site design and Passport remain in place.

## Exact package

- Download filename: `Wonder-Codex-Editor-v1.0.0-Direct-UI-Windows-Setup.zip`
- Version: `1.0.0`
- Bytes: `132334940`
- SHA-256: `26e3873c725f9510fcc51652835c33560a5b71efc1ad047722520e7b407aace9`
- Platform: Windows 10/11, 64-bit. Direct UI edition.

The ZIP stays outside this public repository. It contains the Wonder Codex
adapter; TAZmd's Optimizer remains a separate, creator-owned application
downloaded from [TAZmd](https://www.tazmd.nl/corvettes). The editor retains
credit and a link to [GoatFungus NMSSaveEditor](https://github.com/goatfungus/nmssaveeditor)
for its underlying save editor engine.

## Publish the download

Use the existing API Python dependencies and authorized Spaces credentials.
The static site needs no build changes and the API needs no database migration
for this download route.

1. Run `python scripts/stage_editor_release.py /path/to/release.zip` to verify
   the archive against the pinned release's checksum and size. This default
   mode does not upload or change any service.
2. Run the same command with `--upload` to put the verified ZIP in the existing
   Spaces bucket with a private ACL, attachment filename and checksum metadata.
   It uses a separate, version-pinned `editor-releases/` key and does not alter
   any private admin application.
3. Set `EDITOR_DOWNLOAD_APPROVED=true` as an API runtime environment variable
   and deploy the approved source revision for both site components.
4. Click **Download Editor** on the live site. Confirm the downloaded ZIP's
   byte count and SHA-256 match above, and check the desktop/mobile menus.

Until enabled, `/api/downloads/editor` returns an unavailable page and never
reads or signs a storage object. When enabled it checks the pinned package's
stored checksum, length and version, then issues a short-lived attachment link.
Missing or mismatched storage fails closed. The flag defaults to false and
download responses are not cached. Set it back to false to stop issuing new
links; links already issued expire after the configured
`ADMIN_APP_DOWNLOAD_SECONDS` (default 600 seconds).

Local save editing does not require Passport. Site contributions retain the
existing API requirement for an active Tester or Admin Passport; this release
does not change account permissions.

## Verification

With the API dependencies installed, run:

```sh
cd api
python -m pytest -q tests/test_editor_download.py tests/test_admin_apps.py
cd ..
node tests/site_invariants.test.js
node tests/humanized-public-site.test.js
python scripts/stage_editor_release.py /path/to/release.zip
```

The API checks cover the disabled flag, missing or mismatched packages,
storage failures, the pinned signed redirect, and existing private app
behavior. Archive verification uses the same opened file for hashing and
upload and rejects any package with a different byte count or SHA-256.
