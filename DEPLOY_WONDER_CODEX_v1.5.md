# Deploy Wonder Codex v1.5.0

## Purpose

This release activates local Steam/GOG HG decoding and an Xbox/Game Pass PC WGS reconstruction alpha.

## Safety

- No database migration.
- No new environment variables.
- No Spaces changes.
- Existing image delivery, privacy controls, catalog, verification, and community-submission protections remain included.

## Deploy

1. Upload the complete package contents into the root of the GitHub repository.
2. Preserve the `api/` directory structure and replace existing files.
3. Commit to `main`.
4. Allow the Static Site and Web Service to redeploy.
5. Open `https://wondercodex.com/api/health` and confirm version `1.5.0`.
6. Hard-refresh `https://wondercodex.com/import.html` with `Ctrl + Shift + R`.

## Game Pass test

1. Open the Import page.
2. Click **Choose Xbox/Game Pass folder**.
3. In the Windows picker, press `Ctrl + L` and enter:

   `%LOCALAPPDATA%\Packages\HelloGames.NoMansSky_bs190hzg1sesy\SystemAppData\wgs`

4. Select either the `wgs` folder or the long account-ID folder beneath it.
5. Choose a reconstructed slot marked **Decode locally**.
6. Confirm that the character name appears beside the selected file.
7. Click **Analyze save**.
8. Do not submit the first test until the record counts and character name look correct.

## Failed-layout research

When no slot appears, use **Download metadata-only scan manifest**. The manifest contains redacted paths, sizes, dates, labels, and classifications; it does not contain save-file contents.
