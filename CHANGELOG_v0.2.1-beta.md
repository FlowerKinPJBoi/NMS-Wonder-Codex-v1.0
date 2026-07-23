# Wonder Codex Importer v0.2.1-beta

- Adds `sourceRole`, `sourceCollection`, and `sourceOrdinal` to Pegasus asset records.
- Distinguishes owned ship and multi-tool slots, archived assets, squadron members, fleet frigates, and the current freighter.
- Adds identity-basis, publication-review, special-signal, and delivery-evidence fields required by the Wonder Codex asset review queue.
- Keeps raw saves, local paths, account identifiers, and inventory coordinates out of the exported manifest.
- Updates the asset manifest schema to `wonder-codex-pegasus-asset-manifest/v0.2.1-beta`.

All save access remains read-only. Asset records do not become public automatically.
