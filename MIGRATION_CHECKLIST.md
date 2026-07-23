# Private Repository Migration Checklist

## Phase A — Create private repository

- [ ] Create `Wonder-Codex-Importer` under the correct owner.
- [ ] Set visibility to **Private**.
- [ ] Do not initialize with README, `.gitignore`, or a license.
- [ ] Upload this starter package.
- [ ] Confirm `.github/workflows/build-importer.yml` is present.
- [ ] Confirm `importer-app` is present.
- [ ] Run the private build workflow.
- [ ] Confirm all checks pass and the artifact downloads.

## Phase B — Lock down private repository

- [ ] Invite only necessary collaborators.
- [ ] Disable public forking where available.
- [ ] Require pull requests for future production branches when the team grows.
- [ ] Enable secret scanning and dependency alerts where available.
- [ ] Keep code-signing secrets out until a certificate is purchased.

## Phase C — Clean public repository

- [ ] Delete public `importer-app`.
- [ ] Delete public `build-importer.yml`.
- [ ] Commit the cleanup.
- [ ] Verify website/API deployment still works.
- [ ] Do not publish new proprietary source in the public repository.

## Phase D — Clean-room development

- [ ] Register matched pairs outside Git.
- [ ] Record hashes in `docs/PROVENANCE_LOG.md`.
- [ ] Implement mapping derivation without incompatible source.
- [ ] Add tests before marking a mapping Production.

## Phase E — Public release later

- [ ] Obtain Windows code-signing certificate.
- [ ] Add protected signing workflow.
- [ ] Sign and verify executable.
- [ ] Generate checksum and dependency inventory.
- [ ] Publish signed binary, checksum, release notes, security statement, and notices only.
