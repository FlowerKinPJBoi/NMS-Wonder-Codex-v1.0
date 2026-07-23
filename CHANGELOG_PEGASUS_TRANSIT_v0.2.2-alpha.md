# Pegasus Transit Admin v0.2.2-alpha

## Xbox WGS in-place index commit

- Writes the completed Manual/Auto `containers.index` transaction into the existing file instead of replacing that file with a temporary file.
- Flushes the index transaction through to disk before reporting success.
- Restores the original index bytes and timestamp immediately if the in-place commit fails.
- Adds self-tests that keep an observer handle open to confirm the same index file is updated and that a cancelled write restores its original bytes.

## Evidence

Two v0.2.1-alpha tests produced a locally valid Euclid Manual payload and advanced Manual/Auto WGS generations, but opening No Man's Sky caused Windows Gaming Services to replace those generations with the unchanged cloud payloads before the `?` upload prompt appeared. Decompilation of the known-good GoatFungus write path confirmed that it writes payload and metadata first, then truncates and serializes the existing `containers.index` file through `FileOutputStream`; it does not replace the index file by rename. v0.2.2-alpha changes only this evidence-backed filesystem commit difference.
