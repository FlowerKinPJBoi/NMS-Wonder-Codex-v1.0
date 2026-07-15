# Pegasus Transit operator credentials

The API supports named administrator keys while retaining the legacy `ADMIN_API_KEY` during migration.

Configure this environment variable on the Wonder Codex API service:

```text
ADMIN_API_KEYS={"PJ":"a-long-random-key","Boots":"a-different-long-random-key"}
```

Each operator enters their exact name and matching key. Names are compared case-insensitively; keys remain case-sensitive. Never commit real keys to Git, place them in screenshots, or send both operators the same secret.

Generate independent keys in PowerShell:

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLowerInvariant()
```

After setting `ADMIN_API_KEYS`, redeploy the API and verify both named logins. Keep the legacy `ADMIN_API_KEY` only until all operator clients have been updated, then remove it from the service environment.
