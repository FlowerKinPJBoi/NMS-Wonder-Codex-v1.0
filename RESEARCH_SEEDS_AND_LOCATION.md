# Seeds and location evidence

## Decision

Wonder Codex must treat a procedural seed as specimen identity evidence, not as a galactic coordinate.

A location may be published only when it comes from one of these independent sources:

1. a DiscoveryData Universal Address (UA),
2. a curated portal address tied to the record, or
3. a separately reviewed asset sighting.

The Galactic Cluster Map follows this rule. It never derives a location from an asset seed.

## Evidence from the July 15 export set

### Companion export (`.pet`)

The companion export contains a `CreatureSeed` and a separate `UA`. In the supplied Blob example:

- creature seed: `0x7D66B85AFFEBDE54`
- UA: `0x208BFF11112111`

The values are structurally and numerically different. The same file also has secondary, species, genus, colour, and bone seeds, reinforcing that seeds are generation inputs rather than addresses.

### Starship export (`.sh0`)

The starship export contains a procedural resource filename and resource seed. Its `Location`, `Position`, and `Direction` fields are ownership-slot placement data and do not contain a portal route. This file can support a specimen fingerprint, but not the ship's acquisition system.

### Multi-tool export (`.wp0`)

The multi-tool export contains a seed, resource identity, descriptors, and customization data. It contains no UA or portal address. It can support a specimen fingerprint, but not an acquisition location.

### Freighter backup (`.fb3`)

The supplied file is an `NMSB` binary backup container used by the save editor, not a normalized location-bearing specimen document. Wonder Codex should continue reading freighter identity from the local decoded save through the Importer. It should not upload this binary container or infer a location from its seed.

## What seeds remain useful for

- deduplicating repeated ownership records,
- linking the same procedural specimen across contributors,
- validating that a screenshot and normalized specimen refer to the same generated asset,
- researching modified or special assets,
- joining a later verified sighting to an existing specimen.

Seed equality is not proof that the specimen naturally spawns at the owner's current location. Acquisition locations remain a separate evidence table.
