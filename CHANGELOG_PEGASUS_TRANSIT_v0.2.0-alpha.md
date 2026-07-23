# Pegasus Transit Admin v0.2.0-alpha

## Paired Xbox WGS cloud handoff

- Resolves the selected Xbox character's WGS slot labels from `containers.index` instead of silently editing the newest revision.
- Requires exactly one `Manual` revision and its matching `Auto` revision.
- Patches only the Manual save's `UniverseAddress` and `PreviousUniverseAddress`.
- Advances the paired Auto metadata/descriptor generation without changing its save payload.
- Updates both WGS index entries as one local transaction, matching the verified GoatFungus editor pair.
- Locks Manual, Auto, metadata, descriptors, and `containers.index` between preview and write.
- Creates a complete before-write backup and a best-effort after-local-write evidence snapshot.
- Reports **LOCAL WRITE VERIFIED** and gives the required PC `?` local-upload handoff; it no longer describes a local WGS write as completed cloud transit.

## Required PJ Xbox flow

1. Save in open space on Xbox and fully exit without Quick Resume.
2. Open the PC game to the main menu once to hydrate the current Xbox save, then exit.
3. Run Pegasus Transit and confirm **LOCAL WRITE VERIFIED**.
4. Reopen the PC game to the main menu and upload the newer local save at the `?` prompt.
5. Exit the PC game, then launch Xbox and verify the destination.

The PC does not need to load gameplay.
