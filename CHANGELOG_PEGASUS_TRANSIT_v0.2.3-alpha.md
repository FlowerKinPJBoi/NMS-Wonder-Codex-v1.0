# Pegasus Transit Admin v0.2.3-alpha

## Normal LZ4 save compression

- Replaces the diagnostic literal-only LZ4 encoder with standard fast LZ4 block compression.
- Preserves the existing 512 KiB HG chunk boundaries, headers, trailing null byte, expanded-size metadata, post-write decode verification, paired Manual/Auto transaction, and in-place WGS index commit.
- Adds a multi-chunk compression test that requires substantial size reduction and a successful decoder round trip.
- Adds the MIT-licensed `K4os.Compression.LZ4` 1.3.8 package and its notice.

## Evidence

Both v0.2.2-alpha transactions survived local verification and contained only the intended universe-address patch, but the next PC launch replaced the local generations with unchanged cloud data before the No Man's Sky `?` prompt appeared. Disabling Hello Games cross-save did not change that result, confirming the rejection is below the cross-save UI. The remaining major difference from both native saves and the known-good editor output was physical encoding: Pegasus produced a 2.97 MB literal-only payload from a save normally compressed to roughly 0.61 MB. v0.2.3-alpha corrects that size and encoding profile without changing the route data.
