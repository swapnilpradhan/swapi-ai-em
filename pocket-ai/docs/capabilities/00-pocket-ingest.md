# C0 — Pocket ingest

**Phase:** 1 · **Skill:** `.claude/skills/pocket-ingest` · **Service:** `backend/app/services/{pocket,sync,webhooks}.py`

See [ADR-0008](../adr/0008-webhook-driven-ingest.md).

## Intent

Get recordings from Pocket into the pipeline with no manual step. This is upstream of
everything — if ingest is unreliable, nothing downstream matters.

## Getting an API key

Full walkthrough: [`docs/SETUP_POCKET.md`](../SETUP_POCKET.md).

**Pocket Settings → Developer → API Keys.** The key starts with `pk_`, and can be
regenerated from the same screen. Pocket uses a static key, not OAuth — creating the key
*is* the grant, and it carries no scopes. Verify it with
`GET /api/v1/pocket/status`, which round-trips to Pocket and reports whether transcripts
and speaker labels are actually reachable.

```bash
POCKET_API_KEY=pk_your_key_here
POCKET_API_BASE_URL=https://public.heypocketai.com
```

Auth is `Authorization: Bearer pk_...` (an `ApiKey pk_...` form is also accepted).

**Transcript access appears to require Pocket Pro.** Basic search and account info are
available on all plans; transcripts, folders, and the natural-language query tool are
documented as Pro-only. Since the transcript *is* the ingest payload, a free-plan key
will likely list recordings fine and return nothing useful from the detail endpoint.

## Verifying with MCP (fastest path)

Pocket runs an MCP server at `https://public.heypocketai.com/mcp`. It is **not** part of
the pipeline — see the [ADR-0008 amendment](../adr/0008-webhook-driven-ingest.md) — but
it is by far the quickest way to answer the checklist below, because you can ask
questions of real recordings instead of hand-writing curl.

`.mcp.json` at the project root is already configured:

```json
{
  "mcpServers": {
    "pocket": {
      "type": "http",
      "url": "https://public.heypocketai.com/mcp",
      "headers": { "Authorization": "Bearer ${POCKET_API_KEY}" }
    }
  }
}
```

Export the key and restart Claude Code:

```bash
export POCKET_API_KEY=pk_your_key_here
```

Then ask directly — "pull my most recent recording and show me one raw transcript
segment". That single answer settles whether `speaker` is populated, what the field
names are, and whether timings are seconds or milliseconds.

> **If auth fails with a literal `${POCKET_API_KEY}`:** Claude Code has open bugs where
> `${VAR}` is not expanded inside HTTP-transport headers. Fall back to
> `claude mcp add --transport http pocket https://public.heypocketai.com/mcp --header "Authorization: Bearer pk_..."`,
> which writes the resolved value into local (uncommitted) config.

## ⚠️ Verification checklist

**Corrected against Pocket's published documentation** — base URL and paths are no
longer guesses. The remaining items still need a real key:

- [x] **Base URL:** `https://public.heypocketai.com`
- [x] **Paths:** `/api/v1/public/recordings`, `/api/v1/public/recordings/{id}`
- [x] **Transcript is embedded** in the detail response via `?include=all`, not a
      separate resource. One request, not two.
- [ ] **Field names.** `recordingId`/`recordingTitle`/`recordingDate`/`audioUrl`? → `pocket.py::parse_recording`
- [ ] **Segment units.** Are `start`/`end` seconds (assumed) or milliseconds? Getting this
      wrong silently scales every timestamp by 1000 — check against a known recording length.
- [ ] **Is `speaker` populated?** ← **the highest-value question**, see below
- [ ] **Pagination.** Cursor-based? What is the parameter called?
- [ ] **Signature scheme.** HMAC-SHA256 over the raw body? Is a timestamp included?
      Which headers? → `webhooks.py::verify_signature`
- [ ] **Event names.** → `webhooks.py::KNOWN_EVENTS`
- [ ] **Rate limits.**
- [ ] **Is `audioUrl` pre-signed**, or does it need the Bearer token?
- [ ] **Does your plan return transcripts?** If the detail response has no segments,
      check the plan before debugging the parser.

There is at least one community report of the API not matching its documentation, so
treat a discrepancy as expected rather than as a bug in this code — and correct
`PocketRoutes` when you find one.

The one that changes scope most is `speaker`. If it is reliably populated, diarization
leaves the critical path and Phase 2 loses pyannote, torch, and the GPU requirement.
Pull one recording and look.

## Flow

```
Pocket cloud ──webhook──► POST /api/v1/hooks/pocket
                              │  verify signature (fail closed)
                              │  extract recording id
                              │  202 Accepted  ← fast, before any work
                              ▼
                          background: ingest_recording()
                              │  GET recording + transcript
                              │  dedupe on ExternalRef
                              │  GET audio (optional)
                              ▼
                          existing pipeline
```

Three entry points, **one path** — `services/sync.py::ingest_recording`:

| Entry | Use |
|-------|-----|
| `POST /api/v1/hooks/pocket` | Live webhook |
| `POST /api/v1/pocket/pull` | Manual single recording; `force` re-processes |
| `POST /api/v1/pocket/backfill` | Paginated history walk |

## Requirements

**Only the id is trusted from the payload.** Content is always re-fetched. A forged or
malformed body cannot inject anything into the archive.

**Fail closed.** No `POCKET_WEBHOOK_SECRET` → reject every delivery. An unauthenticated
ingest endpoint lets anyone who learns the URL write into a personal meeting archive.

**Replay protection.** Deliveries older than `POCKET_WEBHOOK_TOLERANCE_SECONDS` (300)
are rejected. Without it a captured delivery stays replayable indefinitely.

**Return 2xx once verified**, including for ignored events. Non-2xx tells the provider
to retry, and retrying something deliberately skipped just generates noise.

**Unknown events still pull.** The taxonomy is unverified and the pull is idempotent:
being wrong costs one redundant fetch, whereas ignoring a real event loses a recording
silently.

**Idempotent.** Delivery is at-least-once. `ExternalRef{provider, external_id, updated_at}`
answers "do we already have this at this revision?" without a fetch. A newer
`updated_at` gets through; an identical one short-circuits.

**Manual tags survive re-sync.** An upstream edit re-fetches the whole transcript.
`_preserve_manual_edits` carries the user's speaker corrections across — silently
discarding them is one of the fastest ways to lose someone's trust.

**Degrade, don't fail.** Audio download failure is a warning, not an error: the
transcript alone still produces every text artifact.

**`recording.completed` can beat transcription.** Empty segments → `NO_TRANSCRIPT`, and
a later transcript event brings us back. This is normal, not a failure.

## Speaker labels

`speaker` becomes `speaker_label`, never `speaker_id`. Upstream tells us *which voice*,
not *which person*. Identification maps labels to enrolled people; until it runs the
segment is unattributed.

When labels are present the pipeline derives turns from them
(`pipeline.py::turns_from_transcript_labels`, merging consecutive same-label segments),
marks diarization `SKIPPED` — not failed, it wasn't needed — and runs identification.

## Identity

| Case | Meeting id |
|------|-----------|
| Audio available | `sha256(audio)` — the same recording imported by file and pulled by API is one meeting |
| No audio | `sha256(recording_id + canonical transcript)` |

The recording-id namespacing in the second case is load-bearing: without audio, two
different recordings can carry identical text, and collapsing them drops one from the
external-ref index.

## Fallback path

`POST /api/v1/meetings` with `raw_transcript` still works, and `parse_transcript()`
still handles `[00:01:23] text` exports — for recordings predating API access, other
devices, and the case where the API is unavailable. It is no longer primary, and the
timestamp-drift correction it does only ever applied to text exports.

## Acceptance criteria

- [ ] Signed delivery → 202, recording ingested
- [ ] Forged signature → 401, nothing ingested
- [ ] Missing secret → 401
- [ ] Stale timestamp → 401
- [ ] Redelivery → `already_current`, no duplicate meeting
- [ ] Genuine upstream edit → re-processed
- [ ] Manual speaker tags survive a re-sync
- [ ] Labelled source → diarization `skipped`, identification `ok`
- [ ] Unlabelled source → diarization runs
- [ ] Missing recording → `not_found`, no crash
- [ ] Bad API key → `failed` with the reason surfaced, not swallowed
- [ ] Empty transcript → `no_transcript`
- [ ] Backfill respects `max_recordings` and terminates
- [ ] Audio download failure still yields a complete text archive

## Local development

Webhooks need a publicly reachable URL. Use a tunnel:

```bash
cloudflared tunnel --url http://localhost:8000
# register https://<tunnel>/api/v1/hooks/pocket in Pocket's webhook settings
```

Without a tunnel, `POST /api/v1/pocket/pull` exercises the identical path.
