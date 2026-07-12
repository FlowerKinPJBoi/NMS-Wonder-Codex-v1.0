# Security and Privacy

## Security promises

- Read-only access to No Man's Sky save files.
- No save editing, overwriting, deleting, renaming, moving, or backup replacement.
- No administrator privileges.
- Raw save bytes remain on the local computer.
- Only the normalized Wonder report shown in the app can be submitted.
- Contributor names can be hidden from public catalog pages.
- No DigitalOcean, Spaces, database, or admin credentials are included in the app.
- No telemetry or background upload.

## Network behavior

The only production network action in v0.1 is an explicit contributor-initiated POST to:

```text
https://wondercodex.com/api/submissions
```

The payload contains normalized discoveries, exact pet matches, review issues, summary counts, contributor attribution choice, character display name, and platform. It does not contain raw save files or local Windows paths.

## Source enforcement

The CI workflow runs `scripts/verify-read-only.ps1`. It rejects source code containing save-modification APIs including:

- `FileAccess.Write`
- `FileMode.Create`, `Truncate`, or `Append`
- `File.WriteAll*`
- `File.OpenWrite`
- `File.Delete`
- `File.Move`
- `Directory.Delete`

Security reports should be handled privately before public disclosure.
