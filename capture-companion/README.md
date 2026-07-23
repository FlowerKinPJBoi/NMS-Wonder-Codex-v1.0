# Wonder Capture Companion v0.1.0-alpha

This private Phase 0 application reuses the Wonder Codex Importer's supported Steam and Xbox / Game Pass read-only decoder. It builds a local discovery baseline, detects newly persisted normalized discoveries, observes new files in a user-selected screenshot folder, and proposes nearby discovery/image pairs for human confirmation.

It does **not**:

- write to a No Man's Sky save;
- inject code into No Man's Sky or read the game's process memory;
- trigger the game's photo interface;
- upload a raw save, screenshot, path, or account identifier;
- automatically confirm or submit a proposed pair.

## Current Phase 0 flow

1. Scan supported saves.
2. Choose the character currently being played.
3. Choose the folder where new screenshots are saved.
4. Start read-only monitoring. Existing discoveries become the session baseline.
5. Discover and scan a specimen in game, take its screenshot, and allow the game to save.
6. Review and confirm any proposed discovery/image pair locally.

The pairing window is three minutes and is intentionally only a suggestion. A human must verify the specimen before any future export or upload step.

## Build

```powershell
dotnet run --project capture-companion/tools/WonderCodex.Capture.SelfTest/WonderCodex.Capture.SelfTest.csproj -c Release
dotnet publish capture-companion/src/WonderCodex.Capture/WonderCodex.Capture.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:PublishTrimmed=false
```

The GitHub Actions workflow produces a Windows x64 trusted-tester artifact and its SHA-256 checksum.
