# Wonder Codex v1.24.0

Production source for the public Wonder Codex website and API at
`wondercodex.com`.

## Repository contents

- Root HTML, CSS, and JavaScript: the deployable static site.
- `assets/`: Wonder Codex glyph and archetype artwork.
- `api/`: FastAPI service, migrations, and API tests.
- `admin/`: browser-based private review and app-vault interfaces.
- `research/`: curated public research fixtures used by the site.

The current release includes the Wonder and procedural-asset catalogs,
contribution and verification workflows, private review tools, original
placeholder artwork, the Galactic Cluster Map beta, contributor ranks, weekly
community missions, the owner-only product questionnaire, and the clean-room
Descriptor Atlas evidence layer. It also includes a private receiver and owner
review lane for locally confirmed Capture Companion discovery/screenshot pairs;
nothing from that lane becomes public without an administrator decision.

v1.18 adds the public Wonder Forge gallery with 95 evidence-labeled fauna
holograms. Thirty verified natural forms can serve as deterministic
representative family artwork on VP/PetData-confirmed catalog records; 65
synthetic NMS-parts variants remain gallery-only. Approved community screenshots
always take precedence and representative art never satisfies exact image
evidence.

v1.18.1 adds a compatible-part preview configurator, restores the richer
galactic stage behind transparent Forge renders, and promotes exact-specimen
screenshot submission to a primary public action.

v1.18.2 makes the Forge stage stars visible at catalog-card scale and prevents
browser autofill from tripping the Screenshot Find spam check.

v1.18.3 keeps the Screenshot Find submit action interactive and displays the
exact missing requirement whenever a restored search value is not a confirmed
catalog selection.

v1.19.0 establishes the optional Galactic Passport account layer: Discord or
email sign-in, contributor profiles, server-enforced access tiers, admin user
management, contribution autofill, and encrypted friend-code storage for future
Wonder Bot services. It also lets non-PC explorers submit a brand-new discovery
screenshot without selecting an existing record; owner approval creates its WC
record and primary image together. Existing tester keys remain available during
migration.

v1.20.0 integrates the expanded Wonder Forge Expedition return: 152 ringless
catalog representatives across fauna, flora, minerals, planets, frigates, and
multi-tools, plus a searchable vault of 329 starship, freighter, and multi-tool
components. Of those representatives, 130 quality-gated forms may support
evidence-safe catalog matching; all planet globes and fourteen uncertain fauna
forms remain gallery-only. Approved screenshots still take precedence,
representative art never changes image evidence, and isolated components are
never presented as finished discoveries.

v1.20.1 adds a client-side representative bridge so those approved holograms
continue to appear on Database cards and records while API deployments catch
up. The Forge now presents complete discovery representatives in a dedicated
collection/family/form projector, separate from the component workshop.

v1.21.0 adds the evidence-backed Planet Hologram Bridge and Star System Census.
Twenty-nine approved planet-family holograms now cover sixteen VP1 families,
including four privacy-safe exact Giant joins and one Gas Giant assignment.
All other planet sizes remain visibly representative because Planet
DiscoveryData does not retain an explicit size field. Planet records are now a
first-class Database and Map filter, while exact community screenshots still
override every representative.

The release also publishes a privacy-reduced 50-system Doshawchuc calibration
set. Its balanced sample shows Yellow F/G, Red K/M, Green E, Blue B/O, and
Purple X/Y separation, with every row paired to retained SolarSystem evidence.
The public fixture deliberately omits raw UAs, VP controls, portal glyphs, and
screenshot filenames. The latest Expedition did not add separately approved
fauna, flora, or mineral forms, so their existing quality-gated imagery remains
unchanged.

v1.22.0 adds 28 clean, ringless close-match representatives for nine confirmed
fauna families: Antelope, Bird, Flying Lizard, Grunt, Proto-Roller, Rodent,
Seahorse, Shark, and Weird Butterfly. This expands approved family coverage
from 11 to 20 of the 33 confirmed live family IDs and improves representative
art for 3,064 mapped fauna records. The site still labels every image as a
family representative rather than an exact specimen, and approved community
screenshots continue to override it.

Branch-only parts, ambiguous scene links, one Antelope assembly with detached
facial pieces, and one tangled Proto-Roller form remain unpublished. Flora and
mineral representatives remain unchanged because their stable VP1 cohorts do
not yet have decoded family semantics.

v1.23.0 adds 20 reviewed close-match views from the focused v0.1.24 assembly
Expedition: Cow, Six-Leg Cow, Two-Leg Antelope, Arthropod, Robot Antelope, and
Small Bird. Confirmed family coverage now reaches 26 of 33 families and improves
representative art for another 1,336 mapped fauna records. The public research
fixture records the chosen inspection angle wherever the opposite view exposed
an assembly seam or detached fragment, and rejects Arthropod Form IV entirely.
The seven families still awaiting evidence-safe imagery remain on the focused
research list.

v1.24.0 adds thirteen complete spacecraft representatives from Expedition
Reviews 31 and 32: Fighter, Hauler, Explorer, Shuttle, Solar, Living Ship,
Sentinel Interceptor, Exotic, Capital Freighter, System Freighter, Small
Freighter, Tiny Freighter, and Pirate Freighter. Previous and future Starship
and Freighter records without approved screenshots now receive a deterministic
representative from the appropriate asset catalog. Fragmented candidates,
detached geometry, effect planes, non-primary LODs, and unresolved optional
branches remain excluded. Exact specimen screenshots still take precedence and
representative art never changes `image_status`.

## Repository boundary

This public repository does **not** contain the Wonder Codex Importer, Pegasus
Transit Admin, Capture Companion, compiled private applications, raw No Man's
Sky saves, decoded private JSON, or production credentials. Those application
sources live in the private `Wonder-Codex-Importer` repository.

## Deployment

DigitalOcean deploys two components from this repository:

1. a Static Site from the repository root;
2. an API Web Service from `/api`, routed at `/api`.

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the current deployment checklist and
[`CHANGELOG.md`](CHANGELOG.md) for release notes.
