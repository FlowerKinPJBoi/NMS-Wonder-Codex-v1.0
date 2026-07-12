# Wonder Codex Importer v0.1.2 — MainWindow Generator Hotfix

## Verified cause

The Avalonia XAML source generator creates fields for controls declared with `Name=` in `MainWindow.axaml`.
`MainWindow.axaml.cs` also manually declared properties with the same names (`AccountList`, `CharacterList`, `AnalyzeButton`, and others).
That produced the verified compiler error `CS0102: MainWindow already contains a definition for ...`.

## Repair

- Removes the duplicate manual control properties.
- Uses Avalonia's generated `InitializeComponent()` method.
- Retains the v0.1.1 restore fix that removed the unavailable `Avalonia.Diagnostics 12.1.0` package.
- Bumps the app and build artifact to v0.1.2.

## Deploy

Upload this package into the repository root, preserving folders and replacing:

- `.github/workflows/build-importer.yml`
- `importer-app/src/WonderCodex.Importer/WonderCodex.Importer.csproj`
- `importer-app/src/WonderCodex.Importer/MainWindow.axaml`
- `importer-app/src/WonderCodex.Importer/MainWindow.axaml.cs`

Commit to `main`. The importer build workflow should start automatically.

No website, API, database, or DigitalOcean changes are required.
