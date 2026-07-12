# Wonder Codex v1.5.0 — Game Pass WGS + Local HG Decoder

## Added

- Xbox App / Game Pass PC folder picker and path guide.
- Recursive WGS structure detection from the package folder, `SystemAppData`, `wgs`, or the account folder.
- `containers.index` slot-label reconstruction.
- Opaque WGS data-file detection using the largest non-container file, matching the live save structure.
- Local No Man's Sky HG chunk decoding with LZ4 block decompression.
- Direct local decoding of current Steam/GOG `save*.hg` character slots.
- Optional local Steam backup-slot decoding.
- Redacted, metadata-only scan manifests for failed folder-layout research.

## Safety

- Folder access is read-only.
- Raw save bytes remain in the browser.
- Only normalized records visible in the preview can be submitted.
- Empty analyses remain blocked from submission.

## Alpha limitations

- Microsoft Store/Xbox folder layouts may vary and require additional structural signatures.
- A valid decoded save can still contain no Wonder structures recognized by the current parser.
- Browser directory access requires the player to choose a folder explicitly.
