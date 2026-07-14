# Wonder Codex v1.7 — Representative Archetypes

## Added

- A safe archetype registry with ten initial SVG scan illustrations.
- Confirmed exact-match family selection for `ANTELOPE`, `CAT`, `FLOATSPIDER`, `HERMITCRAB`, `TREX`, and `TRICERATOPS` fauna.
- Neutral category fallbacks for all other fauna, flora, minerals, and other Wonders.
- Archetype fallback images on catalog cards and discovery record pages.
- Automatic fallback when an approved image is temporarily unavailable.

## Evidence rules

- Approved specimen screenshots always take precedence.
- Specific fauna archetypes require an approved exact pet/discovery match.
- All fallback art is labeled as representative and never presented as a discovered specimen.
- No schema migration is required.

## Deployment

Deploy the static site and API together. The public discovery responses now include `archetype_key`, `archetype_label`, and `archetype_source`. Browser asset query strings have been advanced to `v1.7.0` on the catalog and record pages.
