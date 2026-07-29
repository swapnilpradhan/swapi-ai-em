# Roadmap

Sequenced so each phase is independently useful. If work stops after any phase,
what exists still earns its keep.

The ordering principle: **durability before understanding, understanding before
leverage, leverage before development.** Skipping ahead produces impressive demos
on a foundation that loses data.

---

## Phase 0 — Foundation *(complete)*

Scaffold, domain model, service protocols with working stubs, API surface, docs,
skills. Webhook-driven ingest built against the Pocket API (unverified). No external
credentials required; full test suite green.

**Exit criteria**
- [x] Domain model covers every entity in the capability specs
- [x] Every service protocol has a stub implementation
- [x] `uv run pytest` green with zero credentials
- [x] API serves `/docs` and round-trips a meeting through the stub pipeline
- [x] Every capability has a spec and a skill
- [x] Ingest reworked around webhooks + API ([ADR-0008](adr/0008-webhook-driven-ingest.md))
- [ ] **Pocket API specifics verified against a real key** ← blocks Phase 1 exit

---

## Phase 1 — Durability *(2–3 weeks)*

**Goal:** No recording is ever lost. Everything else depends on this.

### 1.1 Ingest — webhook-driven pull *(built, unverified against the real API)*
- Webhook endpoint with HMAC signature verification and replay protection
- Pull-on-event: the payload supplies only a recording id; content is re-fetched
- Idempotent under at-least-once delivery via `ExternalRef`
- History backfill through the same code path
- Manual speaker tags preserved across re-sync
- **Remaining:** verify endpoints, field names, signature scheme, and event names
  against a real API key — checklist in `docs/capabilities/00-pocket-ingest.md`
- Audio normalization (ffmpeg → 16kHz mono WAV) and quality metrics
- Quarantine path for unusable recordings, with a stated reason

*Superseded: the watch-folder plan and the text-transcript parser as primary path.
File import is retained as a fallback — see [ADR-0008](adr/0008-webhook-driven-ingest.md).*

### 1.2 Google Drive export
- OAuth device/web flow, refresh-token persistence
- Folder tree provisioning: `Pocket.ai Studio/YYYY/YYYY-MM-DD — Title/`
- Resumable upload for large audio
- Idempotent writes keyed on `(meeting_id, artifact_kind)`
- `manifest.json` written to Drive alongside artifacts
- Backoff and resume on quota errors

### 1.3 Reliability
- Dead-letter queue for failed ingests, with retry
- Reconciliation sweep: periodic list-vs-store diff catches missed webhooks
- Alerting when the API key fails or deliveries stop arriving

**Exit criteria**
- Record a meeting; audio + transcript in Drive within 5 minutes, no manual step
- Forged or stale webhook deliveries are rejected
- Redelivery creates no duplicate meeting
- Re-running export creates zero duplicates
- Killing the process mid-upload and restarting resumes rather than restarts
- Deleting the local database and re-syncing from Drive reconstructs export state

**Risks:** Drive quota on large files; OAuth refresh expiry in long-running processes.

---

## Phase 2 — Understanding *(4–6 weeks)*

**Goal:** A transcript you can actually use six months later.

### 2.1 Diarization — *likely unnecessary; verify first*
Pocket returns an optional `speaker` per segment. When present, the pipeline already
derives turns from it and marks diarization `SKIPPED`. **Confirm against a real
recording before building any of the below** — if labels are reliable, this entire
section is deleted along with pyannote, torch, and the GPU requirement.

Only if labels are absent or unreliable:
- pyannote 3.x pipeline behind the `DiarizationService` protocol
- Turn merging and short-segment smoothing
- Quality gate — refuse rather than emit garbage turns
- Graceful degradation to unattributed transcript

### 2.2 Speaker identification
- Voiceprint enrollment: 3+ samples per speaker, consent record required
- Embedding match with a calibrated confidence threshold
- Manual tagging UI; corrections are authoritative and feed the library
- `library_version` bump triggers retroactive re-identification

### 2.3 Summaries and insights
- Three altitudes: one-line, executive paragraph, full brief
- Decisions, risks, open questions, disagreements
- Span citation on every element, with a hard validation pass
- Model routing: fast tier extracts, reasoning tier synthesizes

### 2.4 Action items
- Commitment classification: firm / soft / hypothetical / assigned
- Owner resolution against the speaker roster, `owner_raw` preserved
- Relative date parsing anchored to `meeting.occurred_at`
- Confidence thresholds; low-confidence items queue for confirmation

### 2.5 Mind maps
- Discussion-branch extraction (how the conversation moved, not a topic list)
- Mermaid rendering, spans on every node

**Exit criteria**
- ≥95% speaker-turn accuracy on a held-out labelled set with 3 enrolled samples
- 100% of generated claims carry spans that pass validation
- Action-item precision ≥ 0.85 against user-confirmed ground truth
- Summary + action items available < 90s after ingest

**Risks:** LLM cost per meeting; Pocket's speaker labels being less reliable than they
appear (mitigated — the fallback path is already built and tested).

**Note on overlap:** Pocket's own app produces summaries, action items, and mind maps.
Evaluate each against the real product before building ours. The version worth having
is the grounded, cited, exportable one — but that is a judgement to make with the
competitor's output in hand, not in advance.

---

## Phase 3 — Leverage *(6–8 weeks)*

**Goal:** The corpus does work for you.

### 3.1 Chat with transcripts
- Chunking with speaker + timestamp metadata
- Vector index, incremental updates on new meetings
- Scoped retrieval: single meeting / series / whole corpus
- Hybrid search (semantic + metadata filter) — "what did Priya say about pricing"
  is a filter plus a search, not a similarity guess
- Mandatory citation; explicit refusal when the corpus does not support an answer

### 3.2 Consulting-grade slides
- Structure-first pipeline: governing thought → MECE tree → action titles →
  evidence selection → render
- Structure is reviewable and editable *before* rendering
- House idioms for the major strategy-firm styles (reasoning structures and generic
  professional styling — not firm logos or branded templates)
- `.pptx` output via python-pptx, plus a Markdown structural outline
- Chart generation from meeting data where the argument needs it

### 3.3 Cross-meeting insight
- Theme tracking across a series
- Commitment follow-through: what was promised vs. what recurred unresolved
- Decision archaeology: "when did we decide X, and what changed since"

**Exit criteria**
- A generated deck is usable with < 15 minutes of editing
- Corpus chat answers cite the correct meeting and span ≥ 90% of the time
- Follow-through tracking correctly identifies dropped commitments

**Risks:** Retrieval quality at corpus scale; slide structure quality is the hard
part and rendering is the easy part — resist inverting that.

---

## Phase 4 — Development *(6–8 weeks)*

**Goal:** Measurable growth as an executive communicator.

### 4.1 Rubrics and baseline
- Four tracks: written English, spoken English, thought leadership, thought development
- Explicit, published dimensions per track
- Baseline assessment from existing corpus

### 4.2 Longitudinal scoring
- Per-meeting scoring on spoken tracks
- Document ingestion for written tracks
- Trend analysis over a rolling 90-day window
- Regression alerts on individual dimensions

### 4.3 Coaching loop
- Weekly digest: one strength, one growth edge, both with real clips
- Targeted drills tied to the weakest dimension
- Before/after comparison on the same situation type
- On-demand deep dives ("prep me for the board update")

### 4.4 Thought development
- Idea-maturity tracking: which of your positions are sharpening, which are stalling
- Argument-structure analysis on your own reasoning
- Source diversity and originality signals

**Exit criteria**
- Rubric scores trend measurably over 90 days
- Every coaching point cites a real moment from the user's own material
- Drill completion correlates with dimension improvement

**Risks:** Coaching that feels generic gets abandoned — the entire value is
specificity; rubric validity needs external grounding, not invented dimensions.

---

## Cross-cutting, continuous

- **Cost control.** Track per-meeting LLM spend from Phase 2 onward. Model routing
  and caching are not optimizations to add later; they are Phase 2 requirements.
- **Evaluation.** A labelled fixture set grows from Phase 2. Every prompt change
  runs against it before merge.
- **Privacy.** Consent ledger from Phase 2.1. Retention policy decided before Phase 2 ships.
- **Docs.** Capability specs are updated *before* implementation, not after.

## Explicitly deferred

Real-time assistance · multi-user/team features · mobile · calendar & CRM write-back ·
video · on-device inference · self-hosted model serving.
