# Provenance Record — PAIR-0001

## Scope

This record promotes the first proprietary clean-room compact-key translation
set for the Wonder Codex Importer.

## Matched evidence

| Evidence | Role | SHA-256 | Compared nodes | Accepted mappings | Conflicting keys |
|---|---|---|---:|---:|---:|
| PAIR-0001-Auto-evidence.json | FFC Builder Slot2 Auto | `cd7725b8daf769f27c6b6d8bc932eeb3a4ed1eb25cd0671a6f985271f144231b` | 35,987 | 1,157 | 0 |
| PAIR-0001-Manual-evidence.json | FFC Builder Slot2 Manual | `4216a6867601ddf928f778b367bee157117e38d03ddc2b2689864ee6a9362346` | 35,987 | 1,157 | 0 |

## Corroboration result

- Both evidence reports contain the same 1,157 compact-key to readable-key assignments.
- No compact key conflicts were reported in either matched pair.
- One evidence-score value differs for `n:R -> SaveSummary`; the mapping itself is identical.
- 85 identity entries were omitted from the production translator because they do not rename a key.
- 1,072 effective translations are persisted in `ProductionKeyMapProvider`.
- The supported raw save version is `4733`.
- The production schema identifier is `NMS-4733-PAIR-0001`.

## Functional validation

The Auto pairing reproduced the established FFC Builder normalized profile:

- 3,208 discoveries
- 779 animals
- 703 flora
- 774 minerals
- 34 pets
- 9 exact pet matches
- 156 generation records
- 25 review notes

## Critical Wonder mappings

| Compact | Readable |
|---|---|
| `F2P` | `Version` |
| `<h0` | `CommonStateData` |
| `Pk4` | `SaveName` |
| `Mcl` | `Pets` |
| `fDu` | `DiscoveryManagerData` |
| `8P3` | `DD` |
| `5L6` | `UA` |
| `<Dn` | `DT` |
| `bEr` | `VP` |
| `WTp` | `CreatureSeed` |
| `1p=` | `CreatureSecondarySeed` |
| `m9o` | `SpeciesSeed` |
| `JrL` | `GenusSeed` |
| `UqY` | `GenerationID` |
| `E<S` | `PetBattlerCoreStatClassOverrides` |
| `1o6` | `InventoryClass` |
| `fjE` | `PetBattlerMoveList` |
| `jtr` | `PetBattlerMoves` |

## Data handling

The two evidence files and their source saves remain outside Git. Only their
hashes, derived mapping facts, test assertions, and this provenance summary
are stored in the private repository.

## Confidence

`Corroborated` for version 4733 based on two same-slot Auto/Manual matched
pairs and exact normalized-output reproduction.

The map remains version-gated and is not applied to an unsupported save
version.
