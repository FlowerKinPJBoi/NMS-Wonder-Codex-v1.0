# Wonder Codex Importer v0.1.6 — Automatic Clean-Room Translator

## Added

- Persisted the first independently corroborated proprietary key map.
- Added automatic in-memory translation for compact Xbox/Game Pass save version 4733.
- Automatically resolves the readable character name after translation.
- Automatically analyzes discoveries, pets, exact matches, and generation records without requiring a decoded JSON file.
- Keeps the matched-pair research panel for new versions and independent validation.
- Added production-map self-tests using the confirmed Wonder-critical compact keys.
- Added PAIR-0001 provenance with hashes, corroboration counts, and critical mappings.

## Safety

- Source saves remain opened read-only.
- Translation occurs only in memory.
- No raw save, decoded save, account ID, or evidence file is embedded.
- Unsupported save versions are not automatically translated.
- Submission remains contributor-initiated after preview.

## Supported production schema

`NMS-XBX-4733-PAIR-0001`

The map contains 1,072 effective renames derived from 1,157 conflict-free
accepted mappings corroborated by the FFC Builder Auto and Manual pairs.
