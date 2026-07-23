# Wonder Codex Importer v0.1.4 — WGS Reconnaissance

## What the screenshot verified

The Analyze button ran successfully. The app decoded a JSON object, but the
analyzer found no readable Wonder structures.

The current Xbox scanner also grouped every generic `Detected character`
candidate together by display name. That hid all but the newest candidate in
each account.

## What this build changes

- Preserves one candidate per WGS container instead of collapsing all generic
  candidates into a single row.
- Labels unidentified rows as `WGS candidate 1`, `WGS candidate 2`, and so on.
- Adds a redacted diagnostic preview when a candidate contains zero Wonder
  records:
  - root JSON kind
  - top-level property names
  - object/property counts
  - short-key ratio
  - readable save-marker count
- Keeps submission disabled for empty candidates.
- Reads only. No save file is written, moved, renamed, or deleted.

## Test

1. Upload this patch into the repository root and commit to `main`.
2. Download the new `WonderCodexImporter-v0.1.4-win-x64` artifact.
3. Open the app and select Xbox / Game Pass Account 1.
4. Analyze each WGS candidate.
5. Send a screenshot of the candidate list and the three diagnostic lines for
   a few candidates, especially the largest recent ones.

The diagnostic contains property names and counts only. It does not expose raw
save values, account IDs, or local file paths.
