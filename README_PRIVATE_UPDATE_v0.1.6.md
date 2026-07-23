# Wonder Codex Importer v0.1.6 — Private Repository Update

Upload this package only to the private `Wonder-Codex-Importer` repository.

## Main change

Xbox/Game Pass compact save version 4733 can now be translated automatically
in memory using the independently corroborated PAIR-0001 production map.

The normal test flow is now:

1. Launch the app.
2. Select an account.
3. Select the current large character candidate.
4. Click **Analyze character**.
5. Confirm that the candidate resolves to its character name and produces
   normalized Wonder counts without selecting a decoded JSON file.

The **Pair with decoded JSON** panel remains available only for private
research on new save versions or independent corroboration.

## First validation

Test the same FFC Builder candidate that previously required pairing. Expected:

- FFC Builder
- 3,208 discoveries
- 779 animals
- 703 flora
- 774 minerals
- 34 pets
- 9 exact matches
- 156 generation records

Do not upload or commit the Auto/Manual evidence files, raw WGS saves, or
decoded full JSON exports.
