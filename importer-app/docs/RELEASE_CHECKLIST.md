# Release Checklist

## v0.1 trusted tester

- [ ] GitHub Actions build passes.
- [ ] Read-only source verification passes.
- [ ] HG decoder self-test passes.
- [ ] Message ID self-test passes.
- [ ] App launches on Windows 10/11 x64.
- [ ] PJ's two Xbox / Game Pass accounts are separated correctly.
- [ ] Flower-Kin, PJ's Explorer, Codex Hunter, and FFCBuilder are identified.
- [ ] Steam tester account and characters are identified.
- [ ] Counts match the website importer.
- [ ] Public and private submissions reach the review queue.
- [ ] No local paths appear in the UI or submission payload.

## Before community beta

- [ ] Add signed installer.
- [ ] Publish SHA-256 checksums.
- [ ] Add release notes and privacy policy.
- [ ] Add opt-in diagnostic export with redacted paths.
- [ ] Add update checking without automatic installation.
- [ ] Complete independent code review of the read-only boundary.
