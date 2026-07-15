# Wonder Codex v1.9.0

Full website and API deployment source for the first procedural asset-catalog release.

This version adds:

- separate public catalog lanes for Wonders, starships, freighters, frigates, and multi-tools;
- original Wonder Codex illustrative placeholders for every new asset type;
- permanent `WC-SH`, `WC-FR`, `WC-FG`, and `WC-MT` specimen IDs;
- a strict distinction between an owned procedural specimen and a verified acquisition sighting;
- an admin-only Pegasus manifest importer and asset review/publish queue;
- provenance fields for owned slots, fleet members, squadron members, archived records, and the current freighter;
- explicit privacy rejection when a manifest claims to include a raw save, local path, account identifier, or inventory coordinates.

Database migration `0005_asset_catalog` is required. With `RUN_MIGRATIONS_ON_START=true`, the API applies it during deployment.

See `CHANGELOG_v1.9.0.md` and `DEPLOY_WONDER_CODEX_v1.9.0.md`.
