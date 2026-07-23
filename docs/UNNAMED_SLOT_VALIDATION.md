# Unnamed Game Pass Slot Validation

## Expected account

The account should resolve to four character slots:

- Codex Hunter
- PJ's Explorer
- Flower-Kin
- Unnamed Character

The unnamed character must contain two read-only revisions.

## Required behavior

- The unnamed save is classified from playable character-state structure, not from catalog counts.
- Zero discoveries and zero pets do not make a valid character a metadata object.
- Metadata-only objects remain Research candidates.
- No source file is written, moved, renamed, deleted, or replaced.

## Regression checks

- Named Auto/Manual-style revisions remain grouped.
- FFC Builder and FFC Builder II remain separate characters.
- Steam saves remain grouped by numeric slot, even when two slots share the same SaveName.
