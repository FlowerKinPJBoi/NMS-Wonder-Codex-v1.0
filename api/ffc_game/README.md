# FFC Wilds cloud runtime 0.3.0

Vendored game engine, PostgreSQL adapter, bounded save migration, Discord transport, and private control plane for the FFC community. Only the existing Wonder Codex main API service is used. There is no new DigitalOcean component in this change.

`app.services.ffc_control` supervises `python -m ffc_game.ffc_wilds.cloud_runtime`. `FFC_CLOUD_PREPARED` defaults true; the durable cloud activation flag defaults false. A prepared worker opens no Discord connection. `FFC_DISCORD_BOT_TOKEN` is a runtime secret entered separately during handoff. Existing `DATABASE_URL` and `SPACES_*` values remain in their current environment.

The game uses the `ffc_wilds` schema. Controls, expiring hashed hub sessions, worker heartbeats and a deduplicated command queue use `ffc_wilds_control`. Neither schema alters Wonder Codex's public tables or Alembic history. Game data lives in PostgreSQL; verified private backups use only `ffc-wilds/backups/v1/` in the existing Spaces bucket.

Public readiness: `GET /api/ffc/control/health`. Owner-only handoff and preflight use the existing named owner key. Routine controls exchange that key once for a limited 30-day bearer token; no Discord token is accepted by the control API. The Windows hub stores only its limited bearer using Windows DPAPI.

The separate owner handoff imports a verified canonical save, confirms the PC host stopped, and activates the cloud. Never set activation during a preparatory deployment. Multiple cloud processes share a session-level PostgreSQL ownership lock; a client loses the ability to mutate the game or post publicly when its ownership check fails. Queued commands expire and are bound to a specific host generation. Uncertain deliveries are not replayed.

Rollback before handoff: revert this API change; the PC game is unaffected. Rollback after handoff: deactivate and verify the game ownership lock has been released, preserve the newest cloud save, restore it to a stopped PC host, then restart there. Do not reuse an obsolete pre-handoff save.

The full operator guide and Windows hub source are distributed with the FFC Wilds package. No player saves, connection tokens, owner keys, or production database credentials are committed here.
