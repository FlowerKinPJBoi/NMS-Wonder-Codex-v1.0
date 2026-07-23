# WCCP v0.1 Importer Implementation

The importer creates a data-only Wonder Codex Contribution Package after local analysis. It does not place screenshots or raw-save material in the package.

## User flow

1. Select a detected account and character.
2. Run local analysis.
3. Review WCCP record counts, projector counts, placeholder count, attribution, and the privacy statement.
4. Choose credited or anonymous attribution.
5. Select the save's original platform. A PlayStation, Xbox, Nintendo Switch, or Mac origin requires confirmation that the save reached this PC through official Hello Games cross-save.
6. Select **Export WCCP v0.1** and a destination.
7. The importer creates the package in memory, self-validates it, then writes the validated bytes to the user-selected destination.

The original-platform choice records provenance only. The importer never connects to a console account and continues to read only the local PC save selected during scanning.

## Package layout

```text
manifest.json
discoveries.json
checksums.json
```

No other ZIP entries are permitted.

## Save boundary

Save discovery, decoding, and analysis continue to use the existing `IReadOnlyFileSystem` boundary. The WCCP exporter receives normalized `ContributionSourceRecord` objects only. These objects contain:

- discovery type;
- numeric UA;
- complete ordered VP values;
- calculated projector Message ID when available;
- normalized creature identifier/type when an exact local Pet-to-DiscoveryData match exists; and
- a boolean stating whether the local match occurred.

They do not contain source paths, account IDs, owner blocks, usernames, raw JSON, or raw bytes.

## Self-validation

Before writing the selected export destination, the importer verifies:

- exact ZIP entry names and count;
- compressed and uncompressed limits;
- strict typed JSON with unknown-member rejection;
- manifest version, record count, attribution, and privacy flags;
- source-platform and acquisition-method consistency;
- SHA-256 file checksums;
- 14-hex UA normalization;
- UA-to-portal conversion and glyph sequence;
- ordered VP normalization and seed mappings;
- Base64/payload consistency;
- confirmed 40-byte fauna encoder reconstruction;
- scientific fingerprint recomputation; and
- prohibited owner/account/path fields.

## Archetype placeholders

The importer exports an `archetypeKey`, not an image. The website resolves the key to an exact archetype, family-level, or category fallback illustration. A later moderated screenshot remains linked to the server-assigned permanent WC-ID and does not change the scientific fingerprint.
