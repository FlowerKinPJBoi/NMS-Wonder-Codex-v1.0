# Read-Only Architecture

## Data flow

```text
Known NMS save locations
        ↓ FileAccess.Read only
Account scanner
        ↓
Character list
        ↓ user selection
HG/LZ4 decoder in memory
        ↓
Wonder normalizer in memory
        ↓ review counts and preview
Explicit Submit button
        ↓ HTTPS
Wonder Codex pending review queue
```

## Save-source boundary

All save access is routed through `IReadOnlyFileSystem`. Its public contract provides only:

- existence checks;
- directory and file enumeration;
- file metadata;
- `OpenRead`.

No write method exists on the interface.

## Xbox / Game Pass accounts

The scanner searches:

```text
%LOCALAPPDATA%\Packages\HelloGames.NoMansSky_*\SystemAppData\wgs
```

Every child directory containing `containers.index` is treated as a distinct account. Opaque account IDs are never displayed. HG data blobs are decoded to obtain human-readable character names, and duplicate revisions are collapsed to the newest readable copy of each character.

## Steam accounts

The scanner searches:

```text
%APPDATA%\HelloGames\NMS\st_*
```

Each `st_*` folder becomes a separate account. Current `save*.hg` slots are decoded locally, and duplicate character revisions are collapsed to the newest readable copy.

## No raw-save transmission

`WonderSubmissionClient` accepts only `AnalysisReport`. `AnalysisReport` contains normalized dictionaries matching the existing Wonder Codex submission API. The model has no raw-byte, raw-JSON, or local-path serialization property.
