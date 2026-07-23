# Test Data Policy

## Never commit

- raw `.hg` saves;
- `containers.index`;
- WGS account or container folders;
- decoded full character JSON;
- usernames, account identifiers, friend codes, or local paths;
- screenshots containing credentials or personal identifiers.

## Allowed fixtures

- synthetic JSON created solely for tests;
- redacted structural summaries;
- cryptographic hashes;
- tiny hand-built objects containing no user data;
- normalized Wonder records already approved for public display.

## Matched-pair storage

Real matched pairs must be kept in encrypted private storage outside Git and referenced only by an internal evidence-pair ID and hashes.
