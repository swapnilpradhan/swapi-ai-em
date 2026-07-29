# ADR-0008: Ingest is webhook-driven pull from the Pocket API

**Status:** Accepted · **Date:** 2026-07-29 · **Supersedes:** the watch-folder plan in ROADMAP 1.3

## Context

The original design assumed getting transcripts out of Pocket was the user's problem:
a `POST /api/v1/meetings` endpoint taking a transcript string, plus a planned watch
folder polling a local directory for hand-exported files. The transcript parser was a
regex over `[00:01:23] text` lines.

That assumption was never checked, and it was wrong. Pocket has an official public API
— Bearer auth with `pk_...` keys, endpoints for recordings, transcripts, summaries and
search, plus **webhooks** that fire on processing completion. Transcript segments come
back structured — `{text, start, end, speaker?}` — alongside `recordingId`,
`recordingTitle`, `recordingDate`, `recordingTags` and an `audioUrl`.

Three consequences follow, and the third is the significant one.

## Decision

**Ingest is webhook-driven pull.** A webhook says *what* changed; we fetch the
authoritative copy from the API.

```
Pocket cloud ──webhook──► POST /api/v1/hooks/pocket   verify → extract id → 202
                                   │
                          (background) GET recording + transcript + audio
                                   │
                              existing pipeline
```

**Pull, not push-with-payload.** The webhook body is used for exactly one thing: the
recording id. Everything else is re-fetched. A forged or malformed body therefore
cannot inject content into the archive, and a payload schema change costs us nothing.

**One ingest path.** `services/sync.py::ingest_recording` is the only entry point.
Webhooks, the manual `POST /api/v1/pocket/pull`, and history backfill all go through
it, so dedupe and error handling exist in exactly one place.

**Fail closed on verification.** No configured secret means every delivery is
rejected. An unauthenticated ingest endpoint lets anyone who learns the URL write into
a personal meeting archive.

**Identity.** Audio content hash when audio is available; otherwise a hash of the
transcript *namespaced by the upstream recording id*. The namespacing is not
incidental — without audio, two genuinely different recordings can carry identical
text (a short standup, a repeated phrase), and collapsing them silently drops one from
the external-ref index. `ExternalRef{provider, external_id, updated_at}` is the cheap
dedupe key: at-least-once delivery means redelivery is normal, and it must be
answerable without spending a fetch.

**Skip diarization when the source already labelled speakers.** `speaker?` on each
segment means Pocket has already decided where one voice stops and the next begins.
When labels are present the pipeline derives turns from them, marks diarization
`SKIPPED` (not failed — it wasn't needed), and runs identification only.

## Consequences

**Good**
- Near-real-time, no polling, no manual export step.
- Backfill of existing history reuses the ingest path exactly.
- The regex parser and its timestamp-drift correction are no longer on the primary
  path — numeric timings arrive from the API. That gotcha only ever applied to text export.
- **pyannote, torch, and the GPU dependency may leave the critical path entirely.**
  If `speaker` is reliably populated, Phase 2 collapses from *diarization +
  identification* to identification alone. [ADR-0003](0003-diarization-separate-from-identification.md)
  splitting those stages turns out to be load-bearing for a reason not anticipated when
  it was written: the expensive half may not be ours to do.

**Bad**
- A hard dependency on Pocket's API remaining available and stable. The file-import
  path is retained as the escape hatch.
- Webhook delivery needs a publicly reachable endpoint — a tunnel in local development.
- Endpoint paths, field names, the signature scheme, and the event taxonomy are all
  **unverified** (see below). Some of them are probably wrong.
- An upstream transcript edit re-fetches the whole transcript, which risks discarding
  the user's manual speaker tags. `_preserve_manual_edits` carries them across; that is
  extra machinery that would not exist under a push model.

**Neutral**
- Background processing means the webhook returns before work completes. Correct for
  provider timeouts, but it means failures surface in logs rather than in a response.

## Unverified, and how that is contained

`docs.heypocketai.com` blocks automated fetching, so the specifics came from public
documentation summaries rather than the spec. Everything provider-specific is
centralized so corrections are contained:

| Unknown | Where it lives | Cost if wrong |
|---------|----------------|---------------|
| Endpoint paths | `services/pocket.py::PocketRoutes` | One dataclass |
| Field names | `services/pocket.py::parse_*` | Tolerant already — accepts several spellings |
| Signature scheme | `services/webhooks.py::verify_signature` | One function; fails closed |
| Event names | `services/webhooks.py::KNOWN_EVENTS` | None — unknown events still trigger a pull |

The parsers are deliberately tolerant rather than schema-bound: a naming difference
should degrade to a missing optional field, never to a failed ingest. Verification
checklist in [`capabilities/00-pocket-ingest.md`](../capabilities/00-pocket-ingest.md).

## Alternatives considered

**Keep the watch folder.** Requires a manual export per meeting, which is exactly the
friction that stops recordings from ever being revisited.

**Polling the list endpoint.** Simpler — no public endpoint, no signature verification.
Rejected as the primary mechanism: it trades latency against quota, and gets both
wrong at either end of the tradeoff. Retained implicitly as backfill, which is polling
with a bounded purpose.

**Trust the webhook payload directly.** One fewer API call per event. Rejected — it
makes payload authenticity load-bearing for data integrity, and the whole point of the
signature check is that we would rather not bet the archive on it.

**Use the official MCP server** *instead of* the REST API — rejected, but see the
amendment below: the framing of "instead of" was the error, not the assessment.

---

## Amendment (2026-07-29): MCP is complementary, not an alternative

The original "Alternatives considered" dismissed Pocket's MCP server
(`https://public.heypocketai.com/mcp`) in one line. That judgement was right about the
pipeline and wrong about everything else, because it silently assumed there is only one
consumer of Pocket data. There are two, with opposite requirements.

| | Unattended pipeline | Interactive work |
|---|---|---|
| Caller | Background task | A person, or Claude on their behalf |
| Needs | Idempotency, resumability, explicit backoff, pagination control, determinism | Ad-hoc questions, exploration, no fixed schema |
| Right surface | **REST** | **MCP** |

**REST stays the pipeline's surface.** MCP is a tool-calling protocol designed for a
model in the loop. Driving unattended sync through it means either putting an LLM in the
path of a mechanical job — slow, costly, nondeterministic — or writing an MCP client
purely to make what are effectively REST calls. Neither beats `httpx`, and neither gives
the direct control that `ExternalRef` dedupe, resumable uploads, and 429 backoff depend on.

**MCP is added for interactive use**, via `.mcp.json` at the project root. Two things it
does that the REST client cannot:

1. **It closes the verification gap.** Field names, segment time units, and — most
   importantly — whether `speaker` is populated have been open questions for three
   commits, each blocked on someone hand-writing curl. With MCP configured, those are
   answerable in one conversational turn against real recordings. The answer to `speaker`
   alone decides whether pyannote, torch, and a GPU stay in the project.
2. **It makes the corpus queryable before Phase 3 ships.** `transcript-chat` (C6) is
   months out. MCP gives a usable subset of that value immediately, at zero build cost.

### Consequences

- One more surface to keep in mind, and a second place Pocket's API shape is depended
  upon. Contained: `.mcp.json` is nine lines and holds no logic.
- The API key reaches Pocket's own MCP endpoint — the same party that already holds the
  data. No new trust relationship.
- `${POCKET_API_KEY}` expansion keeps the secret out of the committed file. Claude Code
  has open bugs where `${VAR}` in HTTP-transport *headers* is passed through literally;
  if that bites, `claude mcp add --transport http` writes the resolved header into local
  (uncommitted) config instead.
- **Not** a dependency of the application. The pipeline runs identically whether or not
  any MCP server is configured, and no backend code imports it.

### Related, deliberately not done yet

Pocket.ai Studio could *expose* an MCP server over its own processed corpus — grounded
summaries, cited action items, coaching history — so Claude could query the enriched
archive rather than raw recordings. That is a genuinely strong idea and a natural home
for C6, but it belongs after the corpus exists and after span-cited retrieval works.
Recorded here so the option is not rediscovered from scratch.
