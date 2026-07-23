# Clean-Room Universal Translator Protocol

## Goal

Independently derive only the compact-key mappings required for Wonder Codex without copying GPL source code, GPL mapping tables, or proprietary third-party implementation details.

## Allowed evidence

- Raw save files owned or explicitly supplied by a tester.
- Decoded JSON exports created from the same tester's save.
- In-game screenshots and observed behavior.
- Public factual documentation of file locations and container structure.
- Statistical and structural comparisons performed by our own tools.
- Mappings independently confirmed through multiple matched pairs.

## Prohibited evidence

- Source code from GPL save-mapping projects.
- GPL mapping tables, generated mapping files, or copied key dictionaries.
- Decompiled third-party executables.
- Copying names, algorithms, comments, tests, or implementation structure from incompatible code.
- Automated scraping of incompatible-licensed repositories for mappings.

## Required provenance for every accepted mapping

Record:

- compact key;
- readable field name;
- branch/path context;
- evidence pair identifier;
- derivation method;
- date;
- researcher;
- confidence level;
- independent confirmation count;
- notes showing no incompatible source was used.

## Confidence levels

- `Observed`: one matched pair supports the mapping.
- `Corroborated`: two independent pairs support it.
- `Confirmed`: three or more independent pairs or a deterministic structural proof supports it.
- `Production`: confirmed and covered by automated tests.

## Separation of private data

Raw saves and decoded exports stay outside Git. The repository stores only:

- redacted structural fingerprints;
- hashes;
- synthetic fixtures;
- independently derived mapping facts;
- tests that contain no private account data.

## Scope control

Translate only fields required for:

- save/account identity;
- character slot identity;
- pets;
- DiscoveryManagerData;
- DD / UA / DT / VP;
- GenerationID;
- Xeno battle fields.

Do not translate unrelated save branches merely because they are available.

## Review rule

No mapping enters production until its provenance row is complete and a second review confirms that no incompatible source was used.
