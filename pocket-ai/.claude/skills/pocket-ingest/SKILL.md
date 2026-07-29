---
name: pocket-ingest
description: Pull recordings from the Pocket API into the pipeline via webhooks, manual pulls, and history backfill — with signature verification, idempotent redelivery, and speaker-label short-circuiting. Use this skill whenever the user mentions webhooks, ingest, syncing or importing recordings, the Pocket API, backfilling history, or connecting the device to the app. Also use it when debugging duplicate meetings, missed recordings, webhook 401s, replay protection, or transcripts arriving without speakers.
---

# Pocket ingest

Read [`docs/capabilities/00-pocket-ingest.md`](../../../docs/capabilities/00-pocket-ingest.md)
and [ADR-0008](../../../docs/adr/0008-webhook-driven-ingest.md).

## Before you touch anything: some of the spec is still unverified

Base URL and endpoint paths are now corrected against Pocket's published docs:
`https://public.heypocketai.com`, paths under `/api/v1/public/`, and the transcript
arriving on the detail response via `?include=all`. **Field names, the signature
scheme, and event names are still inferred** — `docs.heypocketai.com` blocks automated
fetching, so those came from documentation summaries.

Getting a key: **Pocket Settings → Developer → API Keys** (starts with `pk_`).
Transcript access appears to be Pro-gated — a free-plan key will likely list recordings
but return no segments, which looks exactly like a parser bug and isn't one.

This is contained by design. Everything provider-specific lives in one of four places:

| Unknown | Where |
|---------|-------|
| Endpoint paths | `services/pocket.py::PocketRoutes` |
| Field names | `services/pocket.py::parse_recording` / `parse_segments` |
| Signature scheme | `services/webhooks.py::verify_signature` |
| Event names | `services/webhooks.py::KNOWN_EVENTS` |

If you are correcting the integration against reality, those are the files. Work the
checklist in the capability spec. **Do not scatter provider-specific knowledge
elsewhere in the codebase** — the containment is what makes a correction cheap.

The parsers are tolerant on purpose: they accept several plausible spellings and fall
back rather than raising. A naming difference should cost an optional field, not a
failed ingest. Preserve that when editing.

## The highest-value unknown

**Is `speaker` reliably populated on transcript segments?**

If yes, Pocket has already done the expensive half of attribution — deciding where one
voice stops and the next begins — and diarization leaves the critical path entirely.
Phase 2 collapses to identification alone, and pyannote, torch, and the GPU requirement
disappear from the project.

The code already handles both cases. Pull one real recording and look; the answer
materially changes the roadmap.

## Non-negotiables

**Only the recording id is trusted from a webhook payload.** Everything else is
re-fetched from the API. This is what makes a forged body harmless — it can at worst
cause us to re-fetch a recording we already have. If you find yourself reading
transcript content out of a webhook body, stop: you have made payload authenticity
load-bearing for data integrity.

**Fail closed.** No configured secret means reject every delivery. An unauthenticated
ingest endpoint is a way for anyone who learns the URL to write into someone's personal
meeting archive. `verify_signature` raises when the secret is empty — keep it that way.

**Replay protection.** Reject deliveries outside the tolerance window. Without it a
captured request stays replayable forever.

**Return 2xx once verified, even for events you ignore.** Non-2xx means "retry", and
retrying something deliberately skipped generates noise until the provider gives up.

**Unknown events still trigger a pull.** The taxonomy is unverified and the pull is
idempotent. Being wrong costs one redundant fetch; ignoring a real event loses a
recording silently, and nobody finds out until they go looking for a meeting that
isn't there.

**Everything goes through `sync.py::ingest_recording`.** Webhooks, manual pulls, and
backfill. One path means dedupe and error handling exist once. Adding a second ingest
route that skips it is how the two drift apart.

## Idempotency

Delivery is at-least-once, so redelivery is the normal case, not an edge case.

`ExternalRef{provider, external_id, updated_at}` answers "already have this?" without
spending a fetch. A newer `updated_at` gets through; an identical one short-circuits to
`ALREADY_CURRENT`.

Meeting identity: audio hash when audio exists, otherwise
`sha256(recording_id + canonical transcript)`. **The recording-id namespacing matters** —
without audio, two genuinely different recordings can carry identical text, and
collapsing them silently drops one from the external-ref index. There is a regression
test for this; it caught a real bug.

## Manual tags must survive re-sync

An upstream edit re-fetches the whole transcript, which would otherwise discard the
user's speaker corrections. `_preserve_manual_edits` carries them across.

Manual tags are authoritative and permanent. Quietly losing them is one of the fastest
ways to make someone stop trusting the system — they corrected it once, watched the
correction vanish, and now they have no reason to correct it again.

## Degradation

| Situation | Behaviour |
|-----------|-----------|
| Audio download fails | Warn, continue — transcript alone produces every text artifact |
| Transcript not ready | `NO_TRANSCRIPT`; a later event brings us back. Normal, not a failure |
| Recording gone | `NOT_FOUND`, no crash |
| Bad API key | `FAILED` with the reason surfaced — never swallow this, the user needs to know |

## Local development

Webhooks need a public URL:

```bash
cloudflared tunnel --url http://localhost:8000
```

Or skip the tunnel entirely — `POST /api/v1/pocket/pull` runs the identical path.
