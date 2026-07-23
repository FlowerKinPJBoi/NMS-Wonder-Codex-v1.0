# Wonder Codex changelog

## v1.17.0 — Capture Companion private review bridge

- Added a credentialed Capture Companion receiver for one locally confirmed
  normalized discovery + screenshot pair at a time.
- Added a dedicated PJ/Boots owner-review lane that keeps incoming pairs private
  until an administrator publishes or rejects the discovery and image together.
- Added Capture-pair counts, previews, normalized discovery evidence, and
  one-action approval/rejection controls to the existing review console.
- Extended named tester credentials with `capture:submit` while preserving their
  inability to open the review console or publish catalog data.
- Kept excluded records entirely local to Capture Companion and retained no raw
  saves, local paths, account identifiers, inventory, missions, or bases.
- Added duplicate protection, image validation, object verification, audit
  events, and database migration `0008_capture_submissions`.

## v1.16.0 — Asset identity and Descriptor Atlas evidence

- Added deterministic visual-profile fingerprints for exact pet/discovery pairs.
- Added normalized descriptor-token coverage and cautious token-name research
  hints to fauna records.
- Added public appearance-signal summaries while retaining raw VP values off the
  record page.
- Added an evidence-gated Descriptor Atlas v2 registry and JSON Schema for
  controlled Wonder Projector correlations.
- Clarified current-versus-native class evidence for starships, freighters,
  frigates, and multi-tools.
- Exposed stable procedural-identity fingerprints and explicitly labels
  appearance seeds as identity evidence, not location claims.
- Kept reconstruction language explicit: representative artwork is not the exact
  specimen without an approved specimen image.
- Preserved Galactic Map performance by avoiding lazy loading of PetData raw
  records in the lean map query.
- Preserved the v1.15 questionnaire, owner console, and all newer site features.

## v1.15.0 — Explorer feedback and pricing research

- Added a public four-step feedback questionnaire covering ease of use, UI
  experience, usefulness, task completion, desired changes, and missing features.
- Added $5/month, $10/month, custom-price, and “I wouldn’t pay” research options.
- Made the possible $5 and $10 memberships explicit monthly service-credit
  allotments and asks respondents how many credits each price should include.
- Added a separate privacy-safe feedback table with bounded text, strict option
  validation, a honeypot, origin checks, and a dedicated rate limit.
- Added a PJ-only feedback console with summaries, raw responses, and CSV export.
- Kept questionnaire content separate from anonymous traffic analytics and
  collected no payment details, raw IP addresses, browser fingerprints, files,
  save data, or account identifiers.

## v1.14.1 — Visceral restricted app access

- Added Visceral as a named restricted tester for the private application vault
  and Pegasus Transit.
- Preserved administrator-only catalog review, release upload, and PJ-only
  analytics restrictions.

## v1.14.0 — Wonder Projector Decoder

- Added a public, browser-only Wonder Projector Decoder for supported fauna,
  flora, and mineral Message IDs.
- Decodes the embedded Universal Address into galaxy number, galaxy name, and
  the twelve-glyph portal route without uploading or retaining the Message ID.
- Added a real Blob Message ID as the input example and a one-click example
  loader.
- Added copyable glyph output and an operator-only Pegasus Transit ticket while
  keeping all save-writing capability restricted to the private app.
- Added decoder navigation, privacy-safe success/error analytics, and regression
  vectors for the known Blob route.

## v1.13.3 — Capture Companion private vault release

- Added Wonder Codex Capture Companion as a third private application with an
  isolated storage object and strict inner-ZIP executable validation.
- Added the v0.1.1-alpha testing brief, screenshots, privacy stop rules, and
  downloadable test report to the private app vault.
- Updated the suggested Importer and Pegasus Transit release versions to
  v0.2.2-beta and v0.3.1-alpha.

## v1.13.2 — ReadyFireAim restricted app access

- Added ReadyFireAim as a named restricted tester for the private application
  vault and Pegasus Transit.
- Preserved administrator-only catalog review, release upload, and PJ-only
  analytics restrictions.

## v1.13.1 — Monketsu restricted app access

- Added Monketsu as a named restricted tester for the private application vault
  and Pegasus Transit.
- Preserved administrator-only catalog review, release upload, and PJ-only
  analytics restrictions.

## v1.13.0 — Private owner analytics

- Added privacy-safe, first-party page and feature analytics without third-party
  trackers, cookies, raw IP storage, or raw browser user-agent storage.
- Added an owner-only dashboard at `/admin/analytics/` protected by PJ's named
  administrator credential; other administrators and testers are refused.
- Added visit totals, page trends, live anonymous sessions, referrers, coarse
  device/browser/OS summaries, popular records and assets, feature filters,
  contributions, imports, downloads, and recent anonymous journeys.
- Excluded all administrator routes and honored Do Not Track and Global Privacy
  Control browser signals.
- Added 90-day detailed-event retention with permanent daily aggregate counts
  and an explicit public analytics privacy notice.

## v1.12.0 — Simplified public records and evidence contributions

- Removed raw Universal Address and VP hex fields from public discovery record
  pages while retaining them in the API, database, importer, and admin tools.
- Renamed the public Message ID presentation to Wonder Projector Message ID.
- Combined image submissions and location verifications into one evidence flow
  where contributors can select either evidence type or both.
- Preserved separate moderated image and verification queues behind the unified
  public form.

## v1.11.3 — Map display and catalog visibility hotfix

- Fixed the completed map-loading layer remaining visible over a successfully
  rendered cluster map.
- Removed Solar System records from the public catalog, public totals, and
  cluster map without deleting them or changing importer/contribution capture.

## v1.11.2 — Galactic map performance

- Stopped loading large raw discovery and PetData JSON columns for map views.
- Added short-lived shared caching for privacy-safe map responses.
- Cancelled superseded filter requests and coalesced pan/zoom drawing into one
  animation frame.
- Stopped rebuilding the hotspot DOM during every canvas redraw.

## v1.11.1 — DigitalOcean tester-key hotfix

- Replaced the JSON `TESTER_API_KEYS` setting with four encrypted scalar tester
  variables accepted by DigitalOcean App Platform.
- Made obsolete or malformed `TESTER_API_KEYS` values harmless to API startup.
- Preserved restricted download and Pegasus Transit scopes for the four named
  testers.

## v1.11.0 — Galactic community foundation

- Added a public contributor leaderboard with original C, B, A, and S galactic
  rank badges.
- Added weekly contribution missions based only on published or approved public
  evidence.
- Added original Pegasus-constellation ambience without replacing the existing
  Wonder Codex visual system.
- Added scoped tester credentials for private-app downloads and Pegasus Transit
  without review-console or build-upload authority.
- Kept PJ and Boots as full administrators and kept all secret values in
  encrypted deployment configuration.

## v1.10.0 — Galactic Cluster Map beta

- Added the interactive Galactic Cluster Map at `map.html`.
- Added galaxy, catalog-lane, Wonder-type, fauna-family, route-evidence, text,
  and display-mode filters.
- Added cluster inspection, pan/zoom, densest-cluster navigation, and heatmap
  mode.
- Added the privacy-safe public `GET /map-points` API.
- Added signed portal-coordinate decoding validated against verified Pegasus
  vectors.
- Restricted asset map points to published specimens with separately verified
  acquisition sightings.

## v1.9.0 — Procedural asset catalog

- Added separate catalog lanes for starships, freighters, frigates, and
  multi-tools.
- Added original Wonder Codex placeholder artwork and permanent asset record
  identifiers.
- Added an admin-only Pegasus asset manifest importer and review/publish queue.
- Added source-role provenance for owned, fleet, squadron, archived, and
  current records.
- Added strict privacy rejection for manifests claiming raw-save, local-path,
  account-identifier, or inventory-coordinate content.

Earlier development history remains available in Git history.
