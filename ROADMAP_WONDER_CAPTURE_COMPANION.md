# Wonder Capture Companion roadmap

## Goal

Help PC explorers pair newly recorded discoveries with screenshots while they play, then hand the reviewed package to the Wonder Codex Importer.

## Safety boundary

The first public build should be a read-only Windows companion, not an injected game hook.

- It watches supported local save revisions and screenshot folders.
- It never writes the NMS save.
- It never uploads a raw save.
- It never uploads automatically.
- It presents a local review queue before the user creates or submits a contribution package.
- It stores credentials outside the package and uses the normal public contribution API.

## Phase 0 — capture feasibility harness

1. Reuse the Importer's Steam/GOG and Xbox WGS read-only discovery decoder.
2. Snapshot normalized discovery keys when a supported save revision changes.
3. Diff the previous and current snapshots to identify newly persisted records.
4. Watch the configured Steam/NVIDIA/Windows screenshot folder for a new image.
5. Pair candidates by timestamp and require the user to confirm the record/image match.

This will detect a discovery after the game persists it. It cannot promise an immediate scan-complete event because NMS does not expose an official live discovery API.

## Phase 1 — in-game-friendly capture queue

1. Add a tray notification when a new persisted discovery is detected.
2. Add a configurable global capture hotkey.
3. Open a compact local matching window showing the new WC candidate, current galaxy/glyph evidence, and the latest screenshots.
4. Allow discard, defer, or confirm.
5. Preserve an auditable local event time and file hash without preserving a raw account identifier.

## Phase 2 — Importer handoff

1. Export a WCCP contribution containing normalized discovery data and confirmed image associations.
2. Open that package in the Importer for privacy preview.
3. Let the contributor choose attribution and explicitly submit.
4. Keep discoveries and images reviewable as separate records on the server.

## Optional Phase 3 — live game hook research

A true scan-complete callback would require an unofficial memory/signature hook or a game-data mod. Existing community frameworks demonstrate that hooks are possible, but signature-based integrations can break after game updates and may increase anti-virus distrust.

This phase should proceed only if a stable, narrowly scoped, open-source event can be proven without save writes, multiplayer automation, or hidden uploads. The companion must continue working without the hook.

## Trust and Nexus distribution

- publish source and exact SHA-256 hashes,
- use a conventional installer or portable ZIP with a clear manifest,
- obtain Windows code signing before broad distribution when practical,
- submit release candidates to multi-engine malware scanning,
- document every folder watched and every network request,
- provide a one-click offline mode and uninstall instructions.
