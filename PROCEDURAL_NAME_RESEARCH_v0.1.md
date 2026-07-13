# Wonder Codex Procedural Discovery-Name Research v0.1

## Current conclusion

The procedural display name is **not present in the normalized `DD`, `DM`, or `OWS` blocks** represented in the test workbook. The Wonder Message ID also contains only the UA, type block, and VP values.

The game nevertheless reproduces a stable display name for each Wonder. This strongly suggests that the name is generated deterministically from:

- discovery type (`DT`);
- one or both VP seeds;
- possibly the UA or a hash combining UA + VP values;
- type-specific game naming tables and grammar.

The exact algorithm is not yet decoded.

## Evidence extracted from `Mission-Discovery(1).xlsx`

| Type | Procedural name | UA | VP0 | VP1 |
|---|---|---|---|---|
| Flora | S. WAVEUSPEUM | 11D417097FF7FD | 323760A66339CD41 | BE7F35C9A20996D9 |
| Mineral | MISCHIONITE | 11D417097FF7FD | 442C1FC0335B2915 | 285944A317AB57B8 |
| Flora | P. IRONAKEA | 308E17097FF7FE | B521C99722F21634 | 93262155C521C8CE |
| Mineral | LAPHURITE | 308E17097FF7FE | 718BEDEBAA651EA5 | 50F79D17F4963ECC |
| Flora | U. LOVENAOE | 413317097FF7FD | 01DD0B8F030542CB | B8079D7B378CCC51 |
| Mineral | BEZILITE | 413317097FF7FD | 5414E12DA85B7BDE | 317A60E071048078 |
| Flora | M. GRASPVEMCIA | 30CD17097FF7FD | 003117216C0D4136 | D0409AC1F3F5A647 |
| Mineral | FLUCATE | 30CD17097FF7FD | 1371AF48C4207181 | 5FCE563690A1966A |
| Flora | S. RIVERIBIA | 1103FF11111111 | 8D01BE6AE65B07F0 | 8BA72147379E272A |
| Mineral | NOPRINGITE | 1103FF11111111 | 34C4C1888E917FA1 | D09E5E2E3D41357C |
| Flora | E. TEETHOLOSUM | 208BFF11112111 | 024B1D416BFF2A12 | 535A637B0E58E6D3 |
| Mineral | NADYRODITE | 208BFF11112111 | BA570CFA38C0C9F8 | B2702F9F5BC0ABEC |

The machine-readable version is in `research/procedural_name_pairs_v0.1.json`.

## What the current pairs prove

1. **UA alone is not sufficient.** Flora and mineral records at the same UA have different names.
2. **Discovery type selects a different naming grammar.**
   - Minerals use single invented words, often ending in `-ite`, `-ate`, or a related mineral-like suffix.
   - Flora use an abbreviated genus initial followed by a species-like word.
3. The required record identity is preserved by the Message ID, so the naming inputs should be recoverable from the same normalized record plus the game's deterministic word tables.
4. Six locations / twelve records are enough to define controlled experiments, but not enough to reconstruct the word tables.

## Clean-room isolation experiments

### Experiment N1 — Does the name follow VP0?

Keep constant:

- UA
- DT
- VP1

Change only VP0, then compare the in-game Wonder Catalogue name.

### Experiment N2 — Does the name follow VP1?

Keep constant:

- UA
- DT
- VP0

Change only VP1.

### Experiment N3 — Does UA contribute?

Keep constant:

- DT
- VP0
- VP1

Change only UA.

### Experiment N4 — Cross-player stability

Load the identical Message ID on two accounts/platforms and confirm the generated name is identical.

### Experiment N5 — Type grammar boundary

Reuse the same two VP values and UA while changing only the projector type block between Flora and Mineral. This may be rejected by the game, but if accepted it would show how strongly `DT` controls the grammar.

## Evidence to record for every test

- test ID;
- UA;
- DT;
- VP0;
- VP1;
- Message ID;
- exact displayed name;
- screenshot;
- changed field;
- unchanged fields;
- game version;
- account/platform.

## Production rule

Do not populate `display_name` from a guessed naming algorithm. Until the algorithm is independently reproduced, names should be:

1. manually entered from an in-game screenshot; or
2. marked as `procedural_name_observed` with screenshot evidence.

## Next likely milestone

Once the controlling seed is isolated, collect at least 100 mineral and 100 flora name/seed pairs. That dataset can test whether the game uses:

- direct PRNG selection from syllable tables;
- seed hashing before selection;
- multiple grammar templates;
- type-specific suffix tables;
- UA-dependent reseeding.
