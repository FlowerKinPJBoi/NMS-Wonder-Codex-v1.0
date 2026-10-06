# Editor download — prepared, not released

**Hold this draft and all website changes until PJ confirms TazMD's approval
of the Optimizer integration. Do not merge, deploy, publish the ZIP, or enable
the public download before then.**

Prepared against `main` at `b0513d40fe222d52cd9d9d04ed95d7de7a3ddd6a`.

The homepage's Research and Roadmap navigation, sections, and links back to
those sections are removed. Public headers now offer **Download Editor**, using
`/api/downloads/editor`. The existing site design and Passport remain in place.

## Exact package

- Supplied archive: `Wonder-Codex-Editor-v0.5.1-alpha-Direct-UI-Windows-Setup(1).zip`
- Download filename: `Wonder-Codex-Editor-v0.5.1-alpha-Direct-UI-Windows-Setup.zip`
- Bytes: `132300865`
- SHA-256: `f3e63f3c428db08069c7581f5f46bf2d805f798de4921b9154f790f5e920be9f`
- Platform: Windows 10/11, 64-bit. Direct UI alpha edition.

Only the download filename drops the duplicate `(1)` suffix. Archive bytes,
notices, source, and creator credits remain unchanged. TazMD's Optimizer is a
separate official application downloaded from its creator; this package contains
the Wonder Codex adapter, not the Optimizer executable or implementation.

The ZIP is not committed to this public repository. Do not add it to a public
release or static assets while approval is pending.

## Release after approval

Use the existing API Python dependencies and authorized Spaces credentials.
The static site needs no build changes and the API needs no database migration.

1. Verify PJ has confirmed TazMD's approval. If TazMD requests a different
   package, replace the pinned release filename, checksum, size, and version in
   `api/app/routers/downloads.py` first, then rerun verification.
2. Run `python scripts/stage_editor_release.py /path/to/supplied.zip` to verify
   the local archive. This default mode does not upload or change any service.
3. Run the same command with `--upload` to put the verified ZIP in the existing
   Spaces bucket with a private ACL, attachment filename, and checksum metadata.
   It uses a separate, version-pinned `editor-releases/` key and does not alter
   any private admin application.
4. Set `EDITOR_DOWNLOAD_APPROVED=true` as an API runtime environment variable
   and deploy the approved source revision for both site components. Merge and
   deployment remain separate owner-authorized release actions.
5. Click **Download Editor** on the live site. Confirm the downloaded ZIP's
   byte count and SHA-256 match above, and check the desktop/mobile menus.

Until explicitly enabled, `/api/downloads/editor` returns a friendly unavailable
page and never reads or signs a storage object. After approval it checks the
pinned package's stored checksum, length, and version and issues a short-lived
attachment link. Missing or mismatched storage fails closed. The approval flag
defaults to false and download responses are not cached. Set it back to false
to stop issuing new links; links already issued expire after the configured
`ADMIN_APP_DOWNLOAD_SECONDS` (default 600 seconds).
