# Pegasus Delivery Network — Framework beta

## Umbrella system

### Pegasus Transit

Verified galaxy, glyph, system, and rendezvous routes.

### Pegasus Courier

Human-operated transfer of legitimately multiplayer-transferable inventory items and creature eggs.

### Pegasus Acquisition

Guided or operator-assisted claiming of assets that cannot be directly handed over, including ships, freighters, frigates, multitools, and natural fauna.

### Pegasus Dispatch

Future request intake, operator assignment, scheduling, status, audit, and delivery confirmation.

## Data lifecycle

1. The importer reads a selected character locally.
2. The user chooses collection modules and privacy options.
3. Raw structures are normalized in memory.
4. The user reviews category counts and preview lines.
5. Existing Wonder records may be submitted to the current review queue.
6. Pegasus beta assets remain local and may be exported as a normalized manifest.
7. A later backend migration will accept selected asset categories only after schemas, deduplication, review rules, and consent are approved.

## Planned database parent model

`catalog_asset`

- asset ID and type
- display name and private/public attribution
- source game version and platform family
- normalized seed data
- normalized location data
- verification and confidence status
- image status
- acquisition methods
- delivery-lane eligibility
- review and audit history

Category tables will hold pet, egg, ship, freighter, frigate, multitool, and inventory-specific fields.

## Deployment stages

1. Local importer preview and export — this beta.
2. Capability matrix and human test protocol.
3. Backend asset schema and pending review queue.
4. Public searchable asset sections.
5. Human-operated Pegasus Dispatch pilots.
6. Assisted automation only for proven workflows.
