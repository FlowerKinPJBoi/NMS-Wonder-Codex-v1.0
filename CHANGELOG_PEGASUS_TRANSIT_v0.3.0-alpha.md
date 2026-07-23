# Pegasus Transit Admin v0.3.0-alpha

## Xbox WGS pending-upload transaction

- Marks both the changed Manual and paired Auto WGS entries as `Modified` in
  `containers.index`.
- Changes the global WGS sync flags to `FullyDownloaded`, clearing the
  `FullyUploaded` bit so the local pair is presented as pending cloud upload.
- Parses and validates the version 14 index header instead of relying on the
  empty-name layout observed in one account.
- Retains the v0.2.3 standard LZ4 encoder, paired Manual/Auto generation,
  in-place index commit, full backup, source lock, and post-write decode.
- Adds a self-test that fails unless the entry state and global sync flags are
  both changed to the pending-local-upload values.

## Why this revision exists

The v0.2.3 evidence pair proved that the route JSON, LZ4 payload, metadata,
descriptors, sizes, and index generations were written correctly. On the next
PC launch, WGS restored the cloud payload because the edited entries still
claimed to be `Synched` and the index still claimed to be fully uploaded.
v0.3.0 addresses that transaction-state mismatch directly.

## Test boundary

This remains a private administrator alpha. Keep Xbox closed and out of Quick
Resume, retain both automatic evidence ZIPs, and stop if the PC still does not
show the `?` local-upload prompt.

## Xbox validation — 2026-07-15

PJ completed the first end-to-end Xbox transit with v0.3.0:

- Catalog route: `WC-A-006062`, Galaxy 1 — Euclid, glyphs `4079FB2FD9DD`.
- Pegasus wrote and decoded the paired WGS transaction successfully.
- No Man's Sky displayed the `?` prompt and accepted the newer local save.
- The PC Game Pass app continued to display `Syncing... 0%`.
- Xbox nevertheless detected the new revision as the latest cloud data.
- After selecting that latest cloud revision, the character loaded at the
  requested Euclid destination.

The Game Pass percentage was therefore stale UI state, not evidence that the
cloud upload failed. v0.3.0 is the validated Xbox writer. A proposed v0.3.1
writer rewrite was withdrawn without testing after this success was confirmed.
