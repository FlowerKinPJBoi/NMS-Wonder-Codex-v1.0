# Wonder Codex v1.6 — Confirmed UA Routes & Pegasus Transit

## Live travel routes

- Added the confirmed Universal Address decoder:
  - UA layout: `PSSSRRYYZZZXXX`
  - portal glyphs: `PSSSYYZZZXXX`
  - galaxy number: hexadecimal `RR` + 1
- Added the complete 1–256 galaxy-name lookup.
- Public records now display a portal route whenever a valid UA is present, even before that individual discovery has been revisited.
- UA-derived routes are visibly distinguished from community-verified locations.
- Verification forms are prefilled with the derived galaxy and glyphs.
- The Admin Catalog and Verification panels display UA-derived routes and any curated values.
- Added backend and browser fallback decoders so the route remains available through both API and static-site logic.
- Confirmed test vector:
  - UA `0x208BFF11112111`
  - portal `208B11112111`
  - RealityIndex `255`
  - Galaxy 256 — Odyalutai

## Pegasus Transit

- Adopted **Pegasus Transit** as the official Wonder Codex transit-system name.
- Replaced the older WARP / Wonder Transit / Ferryman wording on the public pages and roadmap.
- Pegasus Transit remains disabled while the request queue and authorized operator process are researched.

## Procedural discovery-name research

- Extracted twelve matched Flora/Mineral name records from `Mission-Discovery(1).xlsx`.
- Added a machine-readable research set at `research/procedural_name_pairs_v0.1.json`.
- Documented the first clean-room isolation experiments for determining whether names follow DT, UA, VP0, VP1, or a combined deterministic seed.
- No guessed procedural names are published.
