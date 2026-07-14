# Wonder Codex v1.8 — Fauna Identity

## Added

- A visible fauna-family identity panel on catalog cards and discovery records.
- Exact PetData behavior labels such as `Predator`, `Prey`, `Passive`, and `Crab`.
- Evidence-safe family inference for discoveries sharing an unambiguous, approved VP1 family mapping.
- A dynamic fauna-family filter populated from approved PetData evidence.
- Catalog search support for friendly and technical family names such as `T-Rex`, `TREX`, `Float Spider`, and `FLOATSPIDER`.
- A public `/api/fauna-families` endpoint with catalog and evidence counts.

## Evidence rules

- Exact PetData matches may publish both family and recorded behavior.
- VP1-related discoveries may publish the family only when all approved evidence for that VP1 agrees.
- Behavior is never copied from one specimen to another.
- Conflicting VP1 evidence produces no inferred family.
- Approved screenshots continue to take precedence over representative archetypes.

## Privacy and attribution

- Removed a community name that did not yet have affirmative permission for public site association.
- No database migration is required.
