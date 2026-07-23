# Wonder Codex Importer v0.2.0-beta

## WCCP v0.1 contribution export

- Added the Wonder Codex Contribution Package v0.1 data model.
- Added a privacy-first export preview to the desktop application.
- Added ZIP export containing exactly `manifest.json`, `discoveries.json`, and `checksums.json`.
- Added SHA-256 content checksums and package self-validation before the selected destination is written.
- Added normalized 14-hex UA and confirmed UA-to-portal derivation.
- Added complete ordered VP preservation and scientific fingerprints.
- Added confirmed fauna projector payload validation.
- Added archetype placeholder keys for catalog entries without screenshots.
- Added anonymous export support that omits the contributor display name.
- Added original-platform provenance for PC, PlayStation, Xbox, Nintendo Switch, Mac, and unknown sources.
- Added explicit official cross-save-to-PC confirmation for console- and Mac-origin contributions; the importer still reads only the local PC copy.
- Added explicit exclusion of screenshots, raw saves, owner fields, account identifiers, and local paths.
- Added FLOATSPIDER and SIXLEGCOW regression fixtures, including VP4 retention and Nintendo Switch cross-save provenance checks.

## Compatibility

- Save access remains read-only through `IReadOnlyFileSystem`.
- Existing Steam and Xbox / Game Pass PC scanning remains unchanged.
- Existing clean-room translation, Pegasus beta export, and legacy direct-review submission remain available.

## Closed-beta note

This is an internal trusted-tester source update. A Windows artifact should be distributed only after the GitHub Actions read-only, dependency, private-data, self-test, publish, and checksum steps pass.
