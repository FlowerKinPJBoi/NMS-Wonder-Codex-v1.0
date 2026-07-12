# Wonder Codex v1.4.2 — Save Finder Classification Hotfix

## Fixed

- Cache JSON files such as `INTRO_FEED_CACHE.JSON` and `SEASON_DATA_CACHE.JSON` are no longer labeled as decoded character saves.
- Raw Steam/GOG `.hg` files are never offered for analysis until the direct decoder is complete.
- The Save Finder now separates decoded exports, raw slots, and ignored auxiliary files.
- A zero-record analysis displays a clear warning rather than a contribution preview.
- The browser refuses to submit zero discoveries / zero pet matches.
- The API independently rejects empty save-data submissions with HTTP 400.

## Existing empty batches

Earlier zero-record test batches contain no discoveries or pet matches. They can be rejected in the Admin Console.

## Database

No migration is required.
