# Pegasus Transit Admin v0.1.2-alpha

- Recognizes current Xbox character state under `BaseContext` without admitting metadata-only files.
- Fixes the Windows build error caused by capturing a span in the WGS metadata search.
- Anchors the WGS quoted entry timestamp to the already unique container index entry instead of incorrectly requiring it to equal the independently recorded binary file time.
- Extends the synthetic self-tests for nested character detection and the observed WGS index field layout.
