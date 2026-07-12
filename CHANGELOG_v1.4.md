# Wonder Codex v1.4 — Private Attribution & Save Finder Alpha

## Added

- Public-attribution privacy controls for save-data submissions, images, and location verifications.
- Reviewer-visible contributor identity while public catalog pages display `Anonymous Contributor` when privacy is selected.
- Public search protection so private contributor and owner names are not searchable.
- Private save-name and owner masking on public records.
- Admin privacy indicators across Data, Images, Verifications, and Catalog review views.
- Admin-only catalog endpoints that retain access to actual contributor information.
- Wonder Save Finder Steam/GOG alpha:
  - permission-based folder selection;
  - fallback folder upload control;
  - recursive local scanning;
  - decoded JSON selection;
  - raw `save*.hg` / `mf_save*.hg` / `accountdata.hg` detection;
  - local metadata-only scan manifest download.

## Database

Migration `0004_private_attribution` adds a non-destructive `public_attribution` Boolean to:

- `submission_batches`
- `discoveries`
- `pet_discovery_matches`
- `location_verifications`
- `image_contributions`

Existing rows default to public attribution.

## Retained

- v1.3.4 private approved-image delivery.
- v1.3.2 chunked large-save submission protection and error references.
- Image review and DigitalOcean Spaces storage.
- Clickable portal glyph keypad.

## Save Finder limitation

The alpha can immediately open decoded JSON files found inside the selected folder. It detects raw Steam/GOG `.hg` slots, but direct raw-save decoding is not yet enabled. A copied disposable Steam/GOG save folder is required to develop and verify that decoder independently.
