# Wonder Codex v1.18.3

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
