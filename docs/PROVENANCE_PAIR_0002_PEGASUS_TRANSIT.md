# Provenance Record — PAIR-0002 Pegasus Transit

## Scope

This user-owned matched pair independently identifies the compact save fields changed by a successful system-level warp. It supports the private Pegasus Transit Admin alpha and does not add save-writing code to the public importer.

## Evidence

| Evidence | Platform | Save version | SHA-256 | Stored outside Git |
|---|---|---:|---|---|
| PAIR-0002 archive | Xbox / Game Pass WGS | 4733 | `25dd4d6750d5466e7aadbc1db9017fdda003e359c9a3c7632d96d275214d454f` | Yes |
| Before payload | Xbox / Game Pass WGS | 4733 | `32ce1139dd41bcbcf2216d904c9eb92739cb9f403a8131a879ccc96e52ec1bcb` | Yes |
| After payload | Xbox / Game Pass WGS | 4733 | `2e123b25c9eb12327837755adc49a8a0e6e4f5ddd66af244e4171ff3567648a3` | Yes |

The destination was a public Wonder Codex catalog location in galaxy 170 with portal glyphs `1081FC250959`. Its normalized universal address is `0x1081A9FC250959`.

## Observed game-level differences

Exactly nine JSON leaf values changed:

- current `UniverseAddress.RealityIndex`;
- current `UniverseAddress.GalacticAddress` X, Y, Z, and system index;
- previous-universe X, Y, Z, and system index, which received the former current address.

Planet index remained zero. No inventory, mission, base, discovery, ownership, account, pet, or progression value changed.

## Observed WGS transaction

- 47 of 53 files were byte-identical.
- One HG/LZ4 save payload changed.
- Its metadata expanded-size field changed consistently with decoded JSON length plus a trailing null byte.
- WGS data and metadata identifiers were rotated through a new descriptor generation.
- The matching `containers.index` entry advanced its descriptor suffix, timestamp, and combined payload length.

## Confidence

`Observed` for the precise location patch and WGS transaction based on one successful user-owned pair. A second independent Xbox trip is required for `Corroborated`. Steam live-storage behavior remains alpha until Boots supplies the first matched Steam pair.
