# Pegasus Collection Beta — Read-only architecture

## Purpose

The beta expands the importer from a Wonder-discovery collector into a local preview tool for procedural and transferable No Man's Sky assets. It is an evidence-collection framework for future database modules and the Pegasus Delivery Network.

## Hard boundary

The app may:

- locate supported save files;
- open them using read-only file access;
- decode and translate them in memory;
- derive normalized, category-specific records;
- show a local preview;
- submit the already-supported Wonder discovery payload;
- export a normalized Pegasus beta manifest only after the user chooses a destination file.

The app may not:

- edit, rename, move, delete, replace, or resave a game save;
- upload the raw save or decoded JSON;
- include the local save path in the beta manifest;
- include platform account IDs or inventory slot coordinates;
- upload new Pegasus asset categories during this beta.

## Modules

### Wonders and routes — live submission

Existing normalized discoveries, Message IDs, UA-derived routes, generation records, and exact pet matches continue through the established review queue.

### Companion pets and Xeno battle profiles — beta

Candidate fields include CreatureID, creature type, UA, procedural seeds, scale, predator flag, egg-modified flag, battle-class overrides, moves, victories, and traits.

### Creature egg signals — beta heuristic

The first beta recognizes egg-like inventory identifiers. These are research signals, not confirmed egg contents. A later module must correlate inventory metadata, source pet, egg history, and transfer tests.

### Starships — beta

Candidate fields include procedural resource filename, seed, inventory class, and base stats. Acquisition location and cross-player reproducibility are not yet inferred.

### Freighters — beta

Candidate fields include resource filename, seed, inventory class, home-system seed, fleet seed, and base stats.

### Frigates — beta

Candidate fields include resource seed, home-system seed, frigate type, class, race, traits, stats, and expedition count.

### Multitools — beta

Candidate fields include resource filename, seed, class, weapon class, and base stats.

### Inventory identifiers — explicit opt-in beta

The beta can list normalized Product/Substance identifiers. Quantities are excluded unless the user explicitly opts in. No inventory coordinates are exported.

## Delivery lanes

The manifest uses research labels only:

- **Pegasus Transit** — route the player to a verified location.
- **Pegasus Courier** — multiplayer handoff research for items or eggs.
- **Pegasus Acquisition** — assistance claiming ships, freighters, frigates, multitools, or naturally occurring assets.
- **Pegasus Dispatch** — future request queue and operator console.

A delivery-lane label does not establish current transferability.
