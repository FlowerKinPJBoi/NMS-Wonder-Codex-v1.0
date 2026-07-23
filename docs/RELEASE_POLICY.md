# Release Policy

## Internal trusted-tester builds

Private GitHub Actions artifacts may be unsigned during research. They must:

- remain inside the private repository;
- be shared only with named trusted testers;
- be clearly labeled pre-release;
- never be linked from the public Wonder Codex website.

## Public builds

Public distribution is blocked until code signing is active.

Every public release must contain:

1. digitally signed `WonderCodexImporter.exe`;
2. successful signature verification log;
3. SHA-256 checksum file;
4. release notes;
5. security and privacy statement;
6. third-party notices;
7. dependency inventory;
8. versioned installer or ZIP;
9. rollback copy of the previous signed release.

## Publishing boundary

The public website and public repository may publish:

- signed binaries;
- checksums;
- release notes;
- user documentation;
- security promises;
- privacy documentation;
- third-party notices.

They must not publish:

- proprietary source;
- Universal Translator mappings;
- private matched-pair evidence;
- code-signing certificates or secrets;
- private diagnostic data.
