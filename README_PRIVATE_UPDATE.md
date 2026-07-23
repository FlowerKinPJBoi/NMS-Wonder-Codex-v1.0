# Wonder Codex Importer v0.1.5 — Private Repository Update

Upload this package only to the private `Wonder-Codex-Importer` repository.

This build adds the clean-room matched-pair research tool:

- Pair a selected WGS candidate with a decoded JSON export from the same slot.
- Derive provisional compact-key mappings locally.
- Apply mappings in memory and rerun Wonder analysis.
- Copy redacted mapping evidence to the clipboard.
- No raw save values, local paths, or account identifiers enter the report.
- No save file is written, moved, renamed, deleted, or edited.

First test:
1. WGS candidate 5 + Slot2Auto.json
2. WGS candidate 6 + Slot2Manual.json
3. Do not commit either JSON file to Git.
