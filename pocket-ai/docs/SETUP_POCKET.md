# Authenticating your Pocket account

Two credentials, doing different jobs. Getting them confused is the usual cause of a
confusing failure.

| Credential | Direction | Purpose |
|---|---|---|
| `POCKET_API_KEY` | **You → Pocket** | Proves it is your account. Grants read access to your recordings. |
| `POCKET_WEBHOOK_SECRET` | **Pocket → You** | Proves an inbound delivery really came from Pocket. |

Only the first grants access to transcriptions. The second is covered at the end.

## Pocket uses an API key, not OAuth

Worth stating plainly, because Google Drive in this same project works completely
differently and the contrast causes confusion:

| | Pocket | Google Drive |
|---|---|---|
| Mechanism | Static API key | OAuth 2.0 + PKCE |
| Consent screen | None | Yes |
| Scopes | None — the key is your whole account | `drive.file` only |
| Expiry | Never, until you regenerate it | Access token hourly, auto-refreshed |
| Revoke | Regenerate the key | In-app, or Google account settings |

There is no "grant access" dialog for Pocket. **Creating the key is the grant.** Once it
exists, anything holding it can read your recordings.

## Getting the key

1. Open Pocket (web app or mobile).
2. **Settings → Developer → API Keys.**
3. Create a key. It starts with `pk_`.
4. Copy it immediately — most providers show a key once.

```bash
# .env
POCKET_API_KEY=pk_your_key_here
POCKET_API_BASE_URL=https://public.heypocketai.com
```

`.env` is gitignored. Never commit the key, and never paste it into a file that gets
shared — unlike a Drive token, it has no scope limiting what it can reach.

## Verifying it worked

"Is the key set" and "does the key work" are different questions. This answers the second:

```bash
make dev
curl -s localhost:8000/api/v1/pocket/status | jq .check
```

**Working, with everything this project needs:**

```json
{
  "ok": true,
  "authenticated": true,
  "recordings_visible": 1,
  "transcript_accessible": true,
  "segment_count": 42,
  "speaker_labels_present": true
}
```

`speaker_labels_present: true` is the finding that matters most — it means Pocket already
separates voices, and local diarization (pyannote, torch, a GPU) leaves the project
entirely. See [ADR-0008](adr/0008-webhook-driven-ingest.md).

**Key rejected:**

```json
{ "ok": false, "authenticated": false,
  "hint": "Check POCKET_API_KEY — Pocket Settings → Developer → API Keys." }
```

**Authenticated, but no transcripts:**

```json
{ "ok": true, "authenticated": true, "transcript_accessible": false,
  "hint": "...Transcript access appears to require Pocket Pro..." }
```

This is the failure most likely to waste your time. Transcripts appear to be gated behind
**Pocket Pro**; basic search and account info are available on all plans. A free-plan key
authenticates fine and lists recordings, then returns nothing useful — which looks exactly
like a bug in our parser and is not one. Check the plan first.

The response deliberately reports *shape only* — counts and booleans, never transcript
text. A diagnostic endpoint has no business echoing meeting content.

## Then pull a real recording

```bash
curl -X POST localhost:8000/api/v1/pocket/pull \
  -H 'Content-Type: application/json' \
  -d '{"recording_id":"<id from your account>"}'
```

Run it twice — the second should return `already_current`, which is the idempotency
guarantee working.

## The webhook secret (separate credential)

`POCKET_API_KEY` lets you read Pocket. `POCKET_WEBHOOK_SECRET` lets you trust what Pocket
sends *you*. Register a webhook in Pocket pointing at:

```
https://<your-public-host>/api/v1/hooks/pocket
```

and put the signing secret Pocket gives you in `.env`:

```bash
POCKET_WEBHOOK_SECRET=whsec_...
```

Without it, **every delivery is rejected**. That is deliberate: an unauthenticated ingest
endpoint lets anyone who learns the URL write into your personal meeting archive.

For local development you need a public URL:

```bash
cloudflared tunnel --url http://localhost:8000
```

Or skip webhooks entirely — `POST /api/v1/pocket/pull` and `POST /api/v1/pocket/backfill`
run the identical code path without one.

> The webhook signature scheme (`webhooks.py::verify_signature`) is still **inferred**
> from convention, not confirmed against Pocket's spec. If verified deliveries are being
> rejected, that function is the one to correct — everything else about the flow is
> independent of it.

## Security notes

- **The key has no scopes.** Unlike Drive's `drive.file`, a Pocket key is all-or-nothing
  over your account. Treat it like a password.
- **Rotate by regenerating** in Settings → Developer → API Keys. The old key stops working
  immediately, so update `.env` in the same sitting.
- **Never logged.** The key does not appear in logs, and status responses report booleans
  and counts rather than content.
- **The MCP server uses the same key.** `.mcp.json` reads `POCKET_API_KEY` from the
  environment, so it inherits the same access — and the same lack of scoping.
