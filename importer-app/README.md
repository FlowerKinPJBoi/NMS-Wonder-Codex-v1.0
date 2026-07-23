# Wonder Codex Importer v0.2.1-beta — Private Trusted-Tester Build

Read-only Windows desktop application for detecting No Man's Sky save accounts and character slots, analyzing Wonder data locally, and submitting only normalized records to the Wonder Codex review queue.

The v0.2.1 beta adds explicit source-role provenance to the privacy-safe Pegasus asset manifest. Starships, freighters, frigates, and multi-tools remain local read-only observations until an admin reviews and publishes them. Valid catalog records do not require screenshots; the website supplies a clearly labeled illustrative archetype.

This directory is part of a private proprietary repository. Earlier public prototype versions remain under their original MIT license; new work after the repository split is proprietary.

## Absolute read-only rule

The app opens game files with:

```csharp
FileMode.Open
FileAccess.Read
FileShare.ReadWrite | FileShare.Delete
```

The source contains no save-writing, deleting, renaming, moving, truncating, or editing operations. CI enforces the rule.

## Build

Run the private GitHub Action:

`Build Wonder Codex Importer — Internal`

Artifacts are internal, unsigned trusted-tester packages. Do not publish them publicly.

## Universal Translator rule

All compact-key mapping work must follow `../docs/CLEAN_ROOM_PROTOCOL.md`. GPL or AGPL mapping code/data is prohibited without a separate commercial agreement.

Independent community project. Not affiliated with Hello Games, Microsoft, Valve, or GOG.
