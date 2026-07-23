# v0.1.5 Clean-Room Pairing Test

## Purpose

Derive provisional compact-key mappings independently from a tester-owned raw WGS candidate and a decoded JSON export from the same account and slot.

## PJ's first test

1. Build the private `v0.1.5-internal` artifact.
2. Open Xbox / Game Pass Account 1.
3. Select WGS candidate 5.
4. Click **Pair with decoded JSON**.
5. Choose `Slot2Auto.json`.
6. Record the mapping count, conflict count, character name, discovery count, and pet count.
7. Repeat with WGS candidate 6 and `Slot2Manual.json`.
8. Click **Copy redacted evidence** after each run and paste the text into two local files outside Git.

## Safety

- No raw save values are copied into the evidence report.
- No local path or account identifier is included.
- No source save is written, moved, renamed, or deleted.
- The provisional map exists only in memory during the test.
- Do not commit the decoded JSON exports to Git.

## Success criteria

The first research success is any of the following:

- the app resolves `FFC Builder` as the character name;
- the provisional translator exposes non-zero discoveries;
- the evidence report identifies stable mappings for `DiscoveryManagerData`, `DD`, `UA`, `DT`, `VP`, `Pets`, or the pet seed fields.
