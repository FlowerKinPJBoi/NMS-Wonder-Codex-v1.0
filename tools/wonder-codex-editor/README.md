# Wonder Codex Editor v1.0.1

Public source and release-review materials for the Wonder Codex Editor desktop
extension, published with the Wonder Codex project.

Version 1.0.1 adds visible feedback for blocked or failed native save actions.
It preserves the game-running guard and existing editing behavior. See
[the patch notes](app/RELEASE-NOTES-1.0.1.txt) and [BUILD.md](BUILD.md).

The original v1.0.0 **Direct UI Windows release** was uploaded as
`Wonder-Codex-Editor-v1.0.0.zip`:

```text
SHA-256: 26e3873c725f9510fcc51652835c33560a5b71efc1ad047722520e7b407aace9
Size:    132334940 bytes
```

The original release name was
`Wonder-Codex-Editor-v1.0.0-Direct-UI-Windows-Setup.zip`. Renaming the ZIP did
not change its contents or fingerprint.

## Source and build coverage

- [app/source](app/source): the current Java source and mission data, including the 1.0.1 save feedback fix.
- [app/tests](app/tests): regression tests, synthetic fixtures and the recorded
  release test results. Some older GUI probes require a Windows desktop or
  external fixtures; the build guide identifies the self-contained checks.
- [app/assets](app/assets): Wonder Codex branding resources.
- [app/integrations](app/integrations): the PowerShell bridge to TAZmd's separately
  installed Corvette Optimizer.
- Installer scripts target the side-by-side 1.0.1 folder; launcher behavior is retained.
- [BUILD.md](BUILD.md): a checksum-verified build of the desktop extension.
- [RELEASE-REVIEW.md](RELEASE-REVIEW.md): release identity, component provenance,
  scan evidence and limitations.

**This is not yet a complete from-source build of every application component.**
The original source and patch tooling for the older `CosmosBridge.jar` have not
been recovered. The build currently requires the exact bridge from the release
ZIP, checks its SHA-256, and compiles the published desktop-extension source
against that bridge and the pinned upstream engine. It does not rebuild
CosmosBridge or the bundled Java runtime.

The source checkout is not an installable Windows package: binary dependencies,
the Java runtime and its large upstream source archive are omitted. Do not run
`SETUP.bat` from this checkout. Use the complete release package for installation.
The [historical release packager](app/tests/build-release.py) is retained for
provenance. The current [save-fix packager](app/tests/package-save-fix.py) overlays
a tested addon onto the exact original setup ZIP, retaining its unchanged bridge,
runtime and third-party source archive. The source-snapshot manifest and
release-evidence directory describe the original v1.0.0 release.

## Credits and ownership

- [GoatFungus No Man's Sky Save Editor](https://github.com/goatfungus/nmssaveeditor)
  supplies the underlying editor engine. The installer obtains its unchanged,
  pinned version from the author's repository.
- [TAZmd's Corvette Optimizer](https://www.tazmd.nl/corvettes) is created and owned
  by TAZmd. Its executable and optimization algorithm are not included here.
  Wonder Codex provides integration and result validation.
- Eclipse Temurin supplies the Java runtime in the Windows release. Its notices
  and matching upstream source archive are included in that release.

See [app/THIRD-PARTY.txt](app/THIRD-PARTY.txt) and [third-party](third-party).
Publication of this review snapshot does not grant a new license to third-party
components or establish permission to relicense them. Existing attribution and
component terms remain applicable.

Wonder Codex Editor is independent of Hello Games, GoatFungus and TAZmd.
