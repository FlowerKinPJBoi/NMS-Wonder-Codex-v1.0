# Trusted Tester Plan — v0.1

## Before testing

1. Close No Man's Sky.
2. Wait for Steam Cloud or Xbox cloud sync to finish.
3. Keep the current Wonder Codex website importer available as a comparison.
4. Do not publish the unsigned build broadly yet.

## Account discovery tests

- PJ: confirm two Xbox / Game Pass accounts appear separately.
- Account containing Flower-Kin, PJ's Explorer, and Codex Hunter should show those character names.
- FFCBuilder's account should appear as a second account.
- A Steam tester should confirm each `st_*` account is separate.

## Character analysis tests

For each selected character, compare the desktop app with a known decoded JSON import:

- character name;
- pet count;
- discovery count;
- animals;
- flora;
- minerals;
- exact pet matches;
- generation records.

Do not submit when the counts are unexpectedly zero or materially different.

## Submission tests

1. Submit one small test character with public attribution.
2. Confirm it enters Admin → Data Submissions.
3. Submit another test with private attribution.
4. Confirm admins see the real contributor while public approved records show Anonymous Contributor.
5. Confirm duplicates are skipped normally.

## Failure evidence

Capture only:

- app status message;
- platform;
- displayed account/character name;
- counts;
- Wonder Codex submission reference or API error reference.

Never share raw saves publicly.
