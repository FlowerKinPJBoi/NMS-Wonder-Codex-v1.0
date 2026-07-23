# Wonder Capture Companion v0.1.0-alpha

- Added a separate, private read-only capture companion.
- Reused the Importer's Steam and Xbox / Game Pass scanners, decoder, key translator, and normalized discovery analyzer.
- Added stable discovery snapshots and SHA-256 scientific fingerprints.
- Added save-revision polling for newly persisted discoveries.
- Added a user-selected screenshot-folder watcher for new image files.
- Added a three-minute nearest-timestamp pairing proposal with mandatory human confirmation.
- Added self-tests, a read-only source audit, a Windows CI artifact, and a controlled tester brief.
- No process injection, save writes, screenshot capture, network upload, or automatic submission is present.
