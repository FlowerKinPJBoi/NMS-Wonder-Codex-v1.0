# Steam Trusted-Test Protocol — v0.1.8

## Standard scan location

`%APPDATA%\HelloGames\NMS\st_*`

## Included live slot files

- `save.hg`, `save2.hg`, ...
- `mf_save.hg`, `mf_save2.hg`, ...

The scanner does not recurse into backup directories and does not treat account metadata or cache files as characters.

## Expected flow

- Steam account detected automatically.
- Compact version-4733 keys translated in memory.
- SaveName recovered when present.
- `save`/`mf_save` files grouped by numeric slot.
- Newest revision selected.
- Raw save remains local and read-only.

## Capture for the first test

- account list;
- character cards;
- Advanced revision details;
- one normalized analysis result;
- any warning or Research candidate card.

Do not submit the first validation run.
