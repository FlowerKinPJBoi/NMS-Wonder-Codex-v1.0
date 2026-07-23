# Pegasus Transit Admin v0.2.1-alpha

## Xbox cross-save upload marker

- Advances the Manual save metadata's 32-bit Unix revision timestamp at offset 288.
- Retains the paired Manual/Auto WGS transaction introduced in v0.2.0-alpha.
- Leaves the Auto payload and metadata content unchanged, matching the verified editor pair.
- Does not clear the cached `Custom` difficulty label; that unrelated editor-side change is not required for the revision marker.

## Evidence

The v0.2.0 paired test correctly patched `Slot3Manual`, refreshed `Slot3Auto`, and advanced both `containers.index` generations. However, its Manual metadata remained byte-for-byte unchanged because the location patch did not alter the expanded JSON length. In the known-good editor pair, Manual metadata also advances a Unix timestamp from the original save time to the edit time. That missing revision marker is the leading evidence-backed explanation for why the No Man's Sky cross-save screen did not offer the newer-local-save `?` upload action.
