# Pegasus Transit Admin — private alpha

Pegasus Transit Admin is a separate, restricted Wonder Codex operator tool. It is not part of the public read-only importer and must not be distributed publicly.

## Supported test paths

- Xbox / Game Pass PC WGS: paired Manual/Auto transaction based on the verified Ezdaranit matched pair and PJ's proven PC cloud-upload workflow.
- Steam: backup-first alpha writer using the same version-gated game-level address patch and the local `save*.hg` / `mf_save*.hg` pair.
- Save version: `4733` only. Unsupported versions stop before any write.

## Operator workflow

### Xbox / Game Pass cloud handoff

1. Fly the selected character into open space on Xbox and save.
2. Fully exit No Man's Sky on Xbox and remove it from Quick Resume.
3. Open No Man's Sky on the PC only as far as the main menu so the latest Xbox save syncs locally, then exit completely. The PC does not need to load gameplay.
4. Launch Pegasus Transit Admin.
5. Enter the operator name and Wonder Codex administrator key. The key is validated over HTTPS and retained only in memory.
6. Scan local saves and choose the exact character.
7. Enter the WC record, galaxy number/name, and 12 portal glyphs.
8. Preview the route. Pegasus must report the slot's `Manual` revision and paired WGS lock.
9. Complete every departure confirmation and click **Engage Pegasus Transit**.
10. After **LOCAL WRITE VERIFIED**, open No Man's Sky on the PC only to the main menu.
11. On the save's `?` prompt, choose to upload the newer local save to the cloud.
12. Exit the PC game completely and allow several minutes for the background WGS upload. The Game Pass percentage may remain at `0%` even after the revision reaches the cloud.
13. Close the PC Xbox/Game Pass app, then launch No Man's Sky on Xbox.
14. Proceed only if Xbox explicitly identifies the new cloud revision as the latest data. Select that latest cloud data and verify the destination. If Xbox does not identify a newer cloud revision, cancel and preserve the evidence backups for review.

Never launch Xbox between steps 9 and 11; doing so can restore the cloud revision over the local transit.

### Steam

1. Fly the selected character into open space and save.
2. Close No Man's Sky completely.
3. Complete authorization, scan, route preview, and the departure checklist.
4. Click **Engage Pegasus Transit**, then reopen the game and verify the destination.

## Safety boundary

- A complete account/save-directory ZIP backup is created before every write.
- Steam locks the selected source hash. Xbox locks the Manual payload, paired Auto payload, both metadata/descriptor generations, and `containers.index`. Any change cancels departure.
- The game process must be closed.
- Only `UniverseAddress` and `PreviousUniverseAddress` are patched.
- The newly written save is decoded and checked against the target before success is reported.
- New HG save chunks use normal LZ4 block compression rather than literal-only diagnostic encoding, keeping the payload near the size profile produced by the game and the verified editor.
- Xbox patches the slot's Manual revision, advances the Manual cloud-revision timestamp, and refreshes its paired Auto metadata/descriptor generation in one index transaction.
- Xbox marks both changed WGS container entries as `Modified` and changes the index sync flags from fully uploaded/downloaded to fully downloaded. This is the pending-local-upload state required for the PC `?` cloud handoff.
- The Xbox transaction rewrites the existing `containers.index` file in place after payload verification. If that index write fails, Pegasus immediately restores the original index bytes and timestamp before reporting failure.
- Xbox creates a second best-effort evidence snapshot after the local transaction, before the PC cloud handoff.
- Steam replaces only the selected `save*.hg` and matching `mf_save*.hg` after validating temporary files.

Backups are stored under:

`%LOCALAPPDATA%\WonderCodex\PegasusTransit\Backups`

If a test fails, do not launch the game again until the backup has been restored.

## Validated Xbox result

Pegasus Transit v0.3.0 completed its first end-to-end Xbox trip on July 15,
2026. The operator traveled through the PC `?` handoff, Xbox recognized the
result as the latest cloud data, and the character loaded at the requested
Euclid catalog destination. During that successful trip, the PC Game Pass app
remained visually stuck at `Syncing... 0%`; that percentage alone must not be
treated as proof of failure.

## First Steam validation for Boots

The first Steam trip is an evidence-gathering alpha test. Preserve copies of the complete `st_*` folder immediately before and immediately after the successful transit, then upload the matched pair privately. Raw saves and account identifiers must never be committed to Git.
