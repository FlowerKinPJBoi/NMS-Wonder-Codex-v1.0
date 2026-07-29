# Wonder Codex changelog

## v1.22.0 — Fauna close-match gallery

- Added 28 clean, ringless representative forms for Antelope, Bird, Flying
  Lizard, Grunt, Proto-Roller, Rodent, Seahorse, Shark, and Weird Butterfly.
- Expanded approved close-match coverage from 11 to 20 of 33 confirmed fauna
  families, improving the representative image shown for 3,064 mapped records.
- Kept every new form behind exact PetData or confirmed VP1 family evidence and
  visibly labeled it “Representative family image — not this exact specimen.”
- Excluded branch-only parts, ambiguous scene links, a detached-face Antelope
  recipe, and a tangled Proto-Roller recipe from publication.
- Recorded the next focused Expedition targets for complete Cow, Six-Leg Cow,
  Two-Leg Antelope, Arthropod, Robot Antelope, and Small Bird assemblies, plus
  direct-scene searches for Plant Cat, Six-Leg Cat, and Strider Glow.
- Left flora and mineral imagery unchanged because their stable VP1 family
  cohorts do not yet have decoded family names.

## v1.21.0 — Planet holograms and stellar census

- Added 29 approved planet-family holograms across 16 VP1 families.
- Mapped all 621 retained Planet discoveries to evidence-safe imagery: four
  exact Giant joins, one Gas Giant, and 616 family-confirmed standard
  representatives whose size remains explicitly non-exact.
- Added Planet as a first-class Database, Map, contribution, API-stat, and WC
  record type, with exact screenshots retaining precedence over holograms.
- Replaced the eight earlier gallery-only biome globes with the complete Planet
  Linker set in the Forge, including searchable Standard and Giant variants.
- Published an interactive, privacy-reduced Star System Census with 50 verified
  Doshawchuc systems, ten observations per Galactic Map color, and the observed
  F/G, K/M, E, B/O, and X/Y spectral-family separation.
- Preserved the current quality-gated fauna, flora, and mineral set because the
  latest Expedition return contained no newly approved replacements.
- Kept generated planet names in capture-needed status; no name is inferred
  from UA or VP controls.

## v1.20.1 — Database representative bridge

- Restored ringless Expedition representatives throughout Database cards,
  discovery records, and asset records when the API has not yet supplied
  `forge_image_url`.
- Kept exact approved screenshots above every representative fallback.
- Enforced the same client-side eligibility boundary as the API: confirmed
  fauna families and approved category pools only; planets, Starships,
  Freighters, and uncertain fauna remain unassigned.
- Added a dedicated Discovery Projector to the Forge with collection, family,
  and form selectors for fauna, flora, minerals, planets, frigates, and
  multi-tools.
- Kept Starship, Freighter, and Multi-tool construction parts in a separate
  component workshop so parts are never presented as complete discoveries.

## v1.20.0 — Ringless Expedition gallery and Component Vault

- Integrated the expanded Wonder Forge Expedition return as 152 ringless
  catalog representatives and 329 isolated Forge components.
- Added representative shelves for fauna, flora, minerals, planets, frigates,
  and multi-tools on a consistent deep-space hologram stage.
- Added a searchable Component Vault with category, compatible family, slot,
  and part selectors across starship, freighter, and multi-tool research.
- Added evidence-safe Database representatives for 130 quality-gated forms
  without changing image status or presenting them as exact specimens.
- Kept all eight planet globes and fourteen uncertain fauna forms gallery-only,
  and kept Starship and Freighter records on neutral archetypes until complete
  representative forms are certified.
- Preserved exact-screenshot precedence, visible representative/component
  labels, the permanent Preserve identity, and the interactive museum mission.

## v1.19.0 — Galactic Passport foundation

- Added optional Discord and email magic-link authentication through a managed
  Supabase Auth boundary; accounts stay disabled until production values exist.
- Added private contributor profiles with Regular, Tester, and Admin access
  tiers, platform and attribution defaults, and encrypted NMS friend-code
  storage for future Wonder Bot services.
- Added the Galactic Passport page and automatic contributor-name/privacy
  population on the Screenshot Find form.
- Added a non-PC **New discovery** screenshot lane that requires no prior Wonder
  record, issues a private intake reference, and assigns the permanent WC number
  only after admin approval.
- Added a dedicated admin queue that can approve a new screenshot into a
  catalog record and its primary image together.
- Added a Users lane to the existing admin console for audited tier and account
  status changes without exposing credentials or NMS friend codes.
- Preserved all existing named admin/tester keys as the migration fallback.

## v1.18.3 — Screenshot Find interaction hotfix

- Keeps “Submit evidence for review” clickable until an upload is actively
  sending or has completed, so hidden client state cannot create a dead button.
- Adds a visible readiness message naming the first missing requirement.
- Adds an explicit selected-record confirmation and clears stale record state
  when restored or manually edited search text no longer represents a selected
  catalog result.
- Uses client-side validation consistently so every click produces actionable
  feedback instead of being intercepted by native form validation.

## v1.18.2 — Forge stage and Screenshot Find hotfix

- Replaced the sub-pixel Forge backdrop with a brighter, irregular deep-space
  stage designed for transparent holograms at both catalog and record sizes.
- Restored the missing CSS rule that keeps the Screenshot Find anti-spam field
  invisible and out of password-manager autofill.
- Prevented a human browser's autofill value from silently diverting a valid
  screenshot, and now requires a real queued image ID before the interface
  reports success.
- Added regression coverage for the Forge stage asset and screenshot evidence
  submission safeguards.

## v1.18.1 — Forge preview and Screenshot Find

- Restored a layered galactic stage behind transparent Forge holograms in the
  gallery and on Database record representatives.
- Added the first progressive Wonder Forge configurator. It reads certified
  recipe traits, offers only compatible downstream parts, previews an existing
  rendered combination, and supports one-click randomization.
- Added complete-form selection for families whose isolated part maps have not
  yet been certified, without implying that flattened renders are composable
  layers.
- Made screenshot submission a primary navigation action, added a prominent
  Contribution Hub shortcut, renamed the public lane “Submit screenshots,” and
  opens direct screenshot links at the correct form.
- Preserved exact-specimen screenshot priority, visible evidence classes,
  gallery-only synthetic variants, and the permanent Preserve language.

## v1.18.0 — Galactic museum and Wonder Forge gallery

- Added a public Wonder Forge gallery with 95 optimized hologram forms across
  Blob, Cat, Float Spider, Hermit Crab, Strider, T-Rex, Triceratops, and Walking
  Building families.
- Separated 30 verified natural reference forms from 65 NMS-parts synthetic
  variants with persistent, plain-language evidence labels.
- Added deterministic VP0-based selection of verified family representatives
  for Database records whose family identity is supported by exact PetData or
  an unambiguous VP1 mapping.
- Kept representative Forge art explicitly non-exact, left `image_status`
  unchanged, and preserved approved community screenshots as the highest image
  priority.
- Added “an interactive, user-contributed museum of the galaxies” to the public
  mission language while preserving the permanent Preserve identity.
- Replaced the tiled white-dot background with an irregular deep-space
  starfield and quieter Pegasus ambience.
- Added public-site invariants and regression tests for image evidence,
  synthetic-gallery boundaries, exact-image priority, and Preserve language.

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
