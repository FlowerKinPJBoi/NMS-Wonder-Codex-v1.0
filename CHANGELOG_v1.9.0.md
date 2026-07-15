# Wonder Codex v1.9.0 — Asset Catalog Foundation

## Public catalog

- Adds Starships, Freighters, Frigates, and Multi-tools beside the existing Wonders lane.
- Adds an asset detail page with permanent Wonder Codex specimen IDs.
- Shows asset identity/class/source provenance separately from acquisition-location evidence.
- Uses four original Wonder Codex scan illustrations when no approved specimen screenshot exists.
- Labels every asset placeholder: “Illustrative reconstruction — not an image of this exact specimen.”

## Admin review

- Adds a protected asset-manifest import form and review queue.
- Every import begins in `review`; manifests cannot publish records directly.
- An asset with an unknown source role cannot be published.
- Curators can confirm provenance, identity basis, image state, special signals, delivery research state, and notes.

## API and database

- Adds `asset_specimens` and `asset_sightings` through migration `0005_asset_catalog`.
- Adds public `/assets`, `/assets/{id}`, and `/asset-types` endpoints.
- Adds protected `/admin/assets` import, list, detail, and update endpoints.
- Rejects unsafe manifest privacy declarations and ignores unsupported asset categories.

## Importer companion release

Wonder Codex Importer v0.2.1-beta emits Pegasus manifest schema `v0.2.1-beta` with source-role provenance. It remains read-only and exports normalized evidence only.
