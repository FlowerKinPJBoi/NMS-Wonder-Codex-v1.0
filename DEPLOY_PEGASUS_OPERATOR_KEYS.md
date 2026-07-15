# Pegasus Transit operator credentials

The API supports named administrator keys while retaining the legacy `ADMIN_API_KEY` during migration.

Configure these encrypted runtime environment variables on the Wonder Codex API service:

```text
ADMIN_API_KEY_PJ=a-long-random-key
ADMIN_API_KEY_BOOTS=a-different-long-random-key
```

`ADMIN_API_KEYS` JSON remains supported for hosts where object-valued environment variables are convenient, but it is not required.

Each operator enters their exact name and matching key. Names are compared case-insensitively; keys remain case-sensitive. Never commit real keys to Git, place them in screenshots, or send both operators the same secret.

Generate independent keys in PowerShell:

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLowerInvariant()
```

After setting the two named variables, redeploy the API and verify both named logins. Keep the legacy `ADMIN_API_KEY` only until all operator clients have been updated, then remove it from the service environment.
