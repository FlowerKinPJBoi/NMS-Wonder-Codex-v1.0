# Deploy Wonder Codex v1.3.2

This is a cumulative hotfix designed to be installed after v1.3.1.

## Replace these files

- `api/app/config.py`
- `api/app/routers/admin.py`
- `api/app/routers/submissions.py`
- `api/app/services/bulk.py` (new)
- `api/app/services/sanitization.py` (new)
- `import.html`

You may also upload the changelog and this deployment guide.

## Deployment

1. Upload the files to the matching paths in the GitHub repository.
2. Commit to `main`.
3. Let both the Web Service and Static Site deploy.
4. Confirm `https://wondercodex.com/api/health` reports version `1.3.2`.
5. Ask the contributor to hard-refresh `import.html` and submit again.

## No changes needed

- No database migration
- No environment-variable changes
- No Spaces changes
- No re-upload of approved images

## If a submission still fails

The importer will now display an `Error reference` UUID. Search the DigitalOcean Web Service Runtime Logs for that UUID to locate the exact exception without exposing database details to the contributor.
