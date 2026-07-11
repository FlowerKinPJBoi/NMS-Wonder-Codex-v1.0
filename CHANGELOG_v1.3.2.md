# Wonder Codex v1.3.2 — Community Submission Hotfix

## Fixed

- Large character submissions are now inserted into PostgreSQL in safe chunks instead of one oversized SQL statement.
- Large approved batches are also published in safe chunks from the Admin Console.
- Save text and raw normalized JSON are cleaned of PostgreSQL-incompatible NUL bytes and lone Unicode surrogates before storage.
- Failed submissions now return a safe error reference that can be matched to the Web Service runtime log.

## Why this was needed

PostgreSQL/psycopg limits a single statement to 65,535 bind parameters. The original importer sent every discovery in one multi-row insert. Flower-Kin's 3,208 discoveries were close to that boundary; a larger community save could cross it and produce a generic HTTP 500 response.

## Database

No migration is required. Existing submissions, published records, images, verifications, and audit history are unchanged.
