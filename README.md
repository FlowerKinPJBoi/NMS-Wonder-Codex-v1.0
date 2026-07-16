# Wonder Codex v1.10.0

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
placeholder artwork, and the Galactic Cluster Map beta.

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
