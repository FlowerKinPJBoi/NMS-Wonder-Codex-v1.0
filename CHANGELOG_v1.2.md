# Wonder Codex v1.2 Changelog

## Added

- Searchable public Wonder Database
- Individual public record pages
- Derived WC IDs by discovery type and immutable database ID
- Portal glyph asset library extracted from PJ's `Glyphs.xlsx`
- Galaxy and 12-glyph travel panels
- Contributions Hub with Save Data, Images, Verification, and Research lanes
- Working location verification submissions
- Admin Verifications queue
- Admin Catalog editor
- Verification and catalog audit events
- Wonder Save Finder roadmap entry
- Wonder Transit / WARP reserved UI
- Image screenshot guide, record selection, local preview, roles, caption, and rights confirmation

## Changed

- Main navigation now uses **Database** and **Contribute**
- The importer is presented as **Save Data Contribution** inside the Contributions ecosystem
- Home roadmap now includes image storage, Save Finder, and Wonder Transit
- API version is now `1.2.0`

## Database

- Migration `0002_catalog_verifications`
- New catalog fields on `discoveries`
- New `location_verifications` table

## Not enabled yet

- Actual image uploads and Admin Images queue processing require DigitalOcean Spaces. The user interface is staged, but no file is transmitted in v1.2.
- WARP remains disabled until an authorized bot/service integration is established.
