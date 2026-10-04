# Wonder Codex Editor contribution contract v1

API version 1.32.3, migration `0019_editor_imports`. Paths below include the production `/api` prefix. This extends the existing review queue; it does not publish contributions automatically.

## Readiness and consent

`GET /api/editor/capabilities` returns `schema: "wonder-codex-editor-import/1"`, `ready`, `passport_ready`, `database_ready`, `max_records: 10000`, `max_request_bytes: 10000000`, `discovery_types`, `asset_types`, `passport_path`, `submission_path`, and `access_tiers: ["tester", "admin"]`. `ready` requires both configured Passport and the exact current database migration. Keep local scanning available when this route is absent or not ready.

`POST /api/auth/editor/start` requires no body. It returns a secret `device_code` (64 URL-safe characters), a readable `user_code` (`XXXX-XXXX-XXXX`), `expires_in: 600`, `interval: 5`, `verification_uri`, and `verification_uri_complete`. The complete URI must be exactly `https://wondercodex.com/account.html?editor=USER_CODE`. Show the readable code and open that URI in the system browser. Never place the secret device code or a session token in a URL.

The browser uses the existing Passport session to POST `/api/auth/editor/approve` with `{user_code, approved, code_confirmed}`. The user must explicitly confirm that the displayed code matches their Editor. Current eligibility remains an active Tester or Admin Passport, evaluated from the server profile. Browser OAuth/JWT credentials remain in the browser.

The Editor polls `POST /api/auth/editor/token` with `{device_code}` no faster than the supplied interval. Pending responses have `status: "authorization_pending"` or `"slow_down"` and an `interval`. Success is `{status:"authorized", access_token:"wcedit_…", token_type:"Bearer", scopes:["import:submit"], contributor_name, public_attribution, access_tier, expires_at}`. Sessions last at most eight hours and have no refresh token. Access is rechecked on every request. Capture Companion tokens cannot import; Editor tokens cannot submit captures, use operator tools, or access Passport account APIs.

Cancel pending sign-in with `POST /api/auth/editor/cancel` and `{device_code}`; cancellation also revokes a token issued in a race with the final poll. `GET /api/auth/editor/session` checks a Bearer session. `POST /api/auth/editor/revoke` revokes it, including after role or account status changes. All Editor endpoint responses are `Cache-Control: no-store`.

## Explicit selected-record upload

`POST /api/editor/imports` requires `Authorization: Bearer wcedit_…`, `Content-Type: application/json`, and an `Idempotency-Key` UUID generated for the reviewed request. Keep the same body and key when retrying an uncertain outcome. A different body under the same profile/key returns 409. New intentional selections use a new key.

```json
{
  "schema": "wonder-codex-editor-import/1",
  "client_version": "WonderCodexEditor/0.4.0-alpha",
  "platform": "Steam",
  "public_attribution": true,
  "discoveries": [
    {"DT":"Mineral", "UA":"0x0000123456789ABC", "VP":["0x0000000000000001","0xFFFFFFFFFFFFFFFF"], "CustomName":"Example mineral"}
  ],
  "assets": [
    {"assetType":"Multitool", "resourceFilename":"MODELS/COMMON/WEAPONS/MULTITOOL.SCENE.MBIN", "seed":"0x0000000000001234", "displayName":"Example tool", "class":"S", "sourceRole":"owned_slot", "sourceCollection":"Multitools", "sourceOrdinal":0}
  ]
}
```

The schema rejects unknown fields, numeric JSON seeds, floats, booleans in numeric fields, and out-of-range hexadecimal values. UA is a 56-bit unsigned address; each VP/seed is a 64-bit unsigned value encoded as a hexadecimal string. No raw save, owner block, account identifier, file-system path, whole asset JSON, or client-chosen attribution is accepted. Save names are not transmitted. Server attribution is the authenticated contributor; public attribution is the request's choice **AND** the profile's consent.

One request contains 1–10,000 total discovery/asset rows, with at most 5,000 assets and a 10 MB body including chunked requests. Each row must validate before anything is imported. Split larger reviewed selections into separately identified requests; retain receipts for already-completed requests. Do not retry validation or permission errors automatically.

Discovery fields:

| Field | Contract |
| --- | --- |
| `DT` | `Animal`, `Flora`, `Mineral`, `Planet`, or `SolarSystem` |
| `UA` | `0x` plus 1–14 meaningful hex digits (leading zeroes accepted to 16) |
| `VP` | Ordered list of 0–32 hex uint64 strings; Animal requires ≥3, Flora/Mineral ≥2 |
| `CustomName` | Optional string, ≤200 characters |
| `CreatureID`, `CreatureType`, `Descriptors` | Optional enrichment from an exact local pet/discovery join only; requires Animal, nonempty CreatureID and ≥4 VP. Descriptors ≤100, each ≤160 ASCII identifier characters. |

Server reconstruction supplies Message IDs for supported Animal/Flora/Mineral layouts. Planet/System entries do not invent a projector encoding. Full ordered VP is preserved; identity hashing extends beyond VP4 where needed. All evidence remains unverified until owner review. Existing site behavior keeps SolarSystem discoveries available for research while excluding them from the public listing.

Asset fields:

| Field | Contract |
| --- | --- |
| `assetType` | `Starship`, `Freighter`, `Frigate`, or `Multitool` |
| `resourceFilename`, `seed` | Required identity for non-Frigates; game-relative `MODELS/...SCENE.MBIN` and nonzero uint64 hex seed |
| `resourceSeed`, `frigateClass` | Required identity for Frigates, instead of filename/seed |
| `displayName`, `class` | Optional name ≤200 characters; current class `C`, `B`, `A`, `S` or empty |
| `sourceRole` | `current`, `owned_slot`, `stored_slot`, `fleet_member`, `squadron_member`, `archived`, `historical`, `template`, `unknown` |
| `sourceCollection`, `sourceOrdinal` | Optional collection identifier ≤120 ASCII identifier characters and ordinal 0–10000 |

The server derives established PGA asset keys and imports through the existing private asset review model. Existing records are **never overwritten**, including published assets or another contributor's name. Current class is explicitly not a native spawn-class claim. No asset location is inferred from a seed. Corvette assemblies, standalone unmatched pets, egg signals and inventory catalog entries are not supported by this endpoint; preserve them locally and display their reason rather than silently reporting them uploaded.

## Results and retries

```json
{
  "ok":true, "submission_id":"UUID", "status":"pending_review", "pending_review":true,
  "accepted":2, "duplicates":0, "rejected":0,
  "queued_records":{"discoveries":1,"pet_matches":0,"assets":1},
  "duplicates_skipped":{"discoveries":0,"pet_matches":0,"assets":0},
  "contributor":"Authenticated Passport name", "public_attribution":false, "replayed":false
}
```

`accepted` and `duplicates` count selected discovery and asset rows. `pet_matches` is supplementary evidence derived from selected Animal records, so it is not counted twice. Identical retries return the stored result with `replayed: true`. A global duplicate under a new request key reports zero accepted rows and the duplicate count. Receipt creation, batch creation, all review rows and the audit event commit together. Failures roll back all of them, leaving the same key retryable.

401 means reauthenticate; 403 means current access denied; 409 means key conflict (or request still in flight); 413 means reduce request size; 422 means a row violates the contract; 429 means wait according to `Retry-After`; 503 means the deployment/database is not ready. No key or authentication fallback bypasses those responses.

## Deployment and validation

The change adds two independent tables; it does not alter Capture session tokens or existing review records. `REQUIRED_DATABASE_REVISION` is `0019_editor_imports`. Startup migration runs before readiness succeeds. The CI PostgreSQL job verifies upgrade, schema readiness, downgrade to 0018/re-upgrade, and the existing 0016 rollback cycle. It also exercises concurrent same-key replay, conflicting-key payloads, and one-time token exchange on PostgreSQL.

Local validation: Editor/Capture API tests, browser consent tests, strict normalized synthetic records, uint64 preservation, full-VP identity, scope isolation, private attribution, duplicate protection, atomic rollback, size/count limits and readiness failure. PostgreSQL-only tests must pass in CI before deployment. No real save, live contribution, browser login or production database is used by these tests.
