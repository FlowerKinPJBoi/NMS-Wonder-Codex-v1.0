# Wonder Codex Importer v0.1.0 — Trusted Tester Source Preview

A read-only Windows desktop app that automatically finds No Man's Sky saves, lets the contributor choose an account and character, analyzes Wonder data locally, and submits only normalized records to the Wonder Codex review queue.

## Current alpha scope

- Xbox App / Game Pass PC account discovery under the standard WGS package location.
- Separate account cards for every WGS account folder containing `containers.index`.
- Steam account discovery under `%APPDATA%\HelloGames\NMS\st_*`.
- Local HG/LZ4 decoding.
- Character-name detection from decoded save data.
- Local Wonder analysis using the same confirmed Message ID layout as the website importer.
- Public or private contributor attribution.
- Direct HTTPS submission to `https://wondercodex.com/api/submissions`.

## Absolute read-only rule

The app opens game files with:

```csharp
FileMode.Open
FileAccess.Read
FileShare.ReadWrite | FileShare.Delete
```

The application source contains no save-writing, deleting, renaming, moving, truncating, or editing operations. `scripts/verify-read-only.ps1` and the CI self-test fail the build if prohibited file-modification APIs appear under `src/`.

The app runs as the current user and does not request administrator access.

## Build a Windows trusted-tester package

### GitHub Actions — recommended

1. Copy this project into an `importer-app` folder in the Wonder Codex repository.
2. Copy `.github/workflows/build-importer.yml` into the repository's `.github/workflows` folder.
3. Commit to `main`.
4. Open **GitHub → Actions → Build Wonder Codex Importer**.
5. Run the workflow manually.
6. Download the `WonderCodexImporter-v0.1.0-win-x64` artifact.

### Local Windows build

Install the .NET 8 SDK, then run:

```powershell
./scripts/build-windows.ps1
```

The self-contained app will be created under `artifacts/win-x64`.

## Tester safety

Use trusted testers first. Keep No Man's Sky closed during early tests and allow Xbox cloud synchronization to finish before launching the importer. The read-only app cannot edit saves, but testing against stable, synchronized files makes decoding results easier to diagnose.

## Project status

This source package has been structurally checked in the ChatGPT build environment, but that environment does not contain the .NET SDK or Windows runtime. The first GitHub Actions build is therefore the first full compile and Windows execution test.

Independent community project. Not affiliated with Hello Games, Microsoft, Valve, or GOG.
