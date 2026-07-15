# Deploy Wonder Codex v1.10.0

Deploy the same source package to both DigitalOcean App Platform components:

1. Static Site — publishes `map.html`, `map.css`, `map.js`, and the navigation updates.
2. API Web Service — publishes `/map-points` and the shared portal-coordinate decoder.

No database migration or new environment variable is required.

After both components report healthy:

1. Open `https://wondercodex.com/map.html`.
2. Hard refresh with `Ctrl+Shift+R`.
3. Confirm Galaxy 1 — Euclid loads.
4. Select Wonders → Fauna → a fauna family such as Blob.
5. Confirm clusters can be selected, zoomed, and opened in the catalog.
6. Switch between Clusters and Heatmap.
7. Confirm an asset lane shows only specimens with verified acquisition sightings.

API smoke checks:

- `https://wondercodex.com/api/health`
- `https://wondercodex.com/api/map-points?galaxy_number=1&catalog_lane=wonders&limit=10`
