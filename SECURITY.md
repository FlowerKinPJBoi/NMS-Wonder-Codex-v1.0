# Security Policy

## Supported builds

Only builds distributed through an official Wonder Codex release channel are supported. Trusted-tester artifacts from private GitHub Actions are pre-release and must not be posted publicly.

## Public importer security guarantees

- Save files are opened with `FileMode.Open` and `FileAccess.Read`.
- The public Wonder Codex Importer contains no save-writing or save-deletion functions.
- The app does not request administrator rights.
- Raw save bytes and decoded raw JSON remain local.
- The only production network action is an explicit contributor-initiated submission of normalized records.
- No DigitalOcean, database, Spaces, admin, or code-signing credentials are embedded in the application.
- No telemetry or background upload.

The private `pegasus-transit-admin` project is a separate restricted operator application and is excluded from public importer builds. It intentionally writes only after administrator authorization, a complete local backup, a locked-source hash check, an explicit departure checklist, and post-write address verification. It must never be included in a public importer artifact or posted publicly.

Pegasus Transit does not embed administrator credentials. Operator keys are entered per session, validated over HTTPS, held in memory only, and cleared from the visible form after authorization.

## Reporting

Use a private GitHub Security Advisory in this repository for vulnerabilities. Do not open a public issue containing private save data, credentials, account identifiers, or exploitable technical details.

## Public-release gate

A public release must not occur unless:

1. read-only source verification passes;
2. dependency policy verification passes;
3. private-save fixture verification passes;
4. all self-tests pass;
5. the executable is digitally signed;
6. the signed executable's signature is verified;
7. a SHA-256 checksum is published;
8. release notes and security documentation are published.

The Pegasus Transit Admin project has no public-release path. Its GitHub Actions artifact is a short-retention private alpha intended only for named Wonder Codex operators.
