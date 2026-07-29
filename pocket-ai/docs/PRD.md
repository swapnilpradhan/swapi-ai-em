# Pocket.ai Studio — Product Requirements

**Status:** Draft v1 · **Owner:** Swapnil Pradhan · **Last updated:** 2026-07-29

---

## 1. Problem

A Pocket.ai device records meetings and produces audio plus a raw transcript.
That is where the value stops. Today:

- Recordings live on the device or in a vendor app, not in the place the user
  actually keeps their working life (Google Drive). There is no durable,
  browsable, portable archive.
- The transcript is an undifferentiated wall of text. It has no speaker labels,
  so a week later it is impossible to tell who committed to what.
- Everything downstream — the summary, the follow-ups, the deck for the steering
  committee — is manual re-reading and re-typing. The time cost is high enough
  that most recordings are never revisited at all.
- The single richest corpus of the user's own communication — hundreds of hours
  of how they actually speak in high-stakes rooms — is sitting unused, while
  executive-communication coaching is generic and expensive.

The gap is not transcription. It is everything between a transcript and a decision.

## 2. Users

**Primary — the operator-executive (the user).** Runs many meetings a week across
engineering, product, and leadership. Needs recall, needs to close loops, needs to
produce board- and exec-grade artifacts fast, and is deliberately investing in
their own communication as a career asset.

**Secondary — meeting participants.** Never touch the product directly, but their
voices are processed and their commitments are extracted. Their consent and
privacy are a first-class design constraint, not a footnote.

**Tertiary (future) — a small team.** Shared meeting series, shared action items,
shared institutional memory. Out of scope for v1 but the data model must not
foreclose it.

## 3. Goals

| # | Goal | Success measure |
|---|------|-----------------|
| G1 | Every recording lands durably in Drive without manual work | 100% of recordings exported within 5 min of availability; zero duplicates |
| G2 | Transcripts are attributed to named humans | ≥95% speaker-turn accuracy on known speakers after 3 enrolled samples |
| G3 | Post-meeting synthesis is near-instant | Summary + action items available < 90s after transcript ingest |
| G4 | The corpus is queryable in natural language | Answers to "what did we decide about X" cite the exact meeting and span |
| G5 | Deck-quality output without a designer | A generated deck is usable with < 15 min of editing |
| G6 | Measurable improvement in communication | Rubric scores trend up over a rolling 90-day window |

## 4. Non-goals (v1)

- Replacing Pocket.ai's on-device transcription. We consume its output.
- Real-time / live-meeting assistance. Everything here is post-hoc.
- Multi-tenant SaaS, billing, org admin.
- Video. Audio and text only.
- Calendar or CRM write-back. Read-only enrichment at most.
- Mobile apps.

## 5. Capabilities

Each links to a full spec. The spec is the contract; the matching skill in
`.claude/skills/` is the execution procedure.

### Phase 1 — Durability

**C1. Google Drive export** ([spec](capabilities/01-drive-export.md))
Push audio + transcript + derived artifacts to a Drive folder tree the user owns.
Deterministic naming, idempotent re-runs, resumable uploads for large audio, a
manifest that survives a database wipe. This is the foundation: it must be boring
and it must never lose data.

### Phase 2 — Understanding

**C2. Speaker diarization and identification** ([spec](capabilities/02-speaker-identification.md))
Two separable problems. Diarization segments audio into "speaker 1 / speaker 2"
turns. Identification maps those anonymous labels to named people via a voiceprint
library the user enrolls once. Manual tagging is always available and always wins
over the model; every correction feeds back into the library.

**C3. Summaries and insights** ([spec](capabilities/03-summaries-and-insights.md))
Three altitudes — one-line, executive paragraph, full brief — plus decisions,
risks, open questions, and disagreements. Every element cites transcript spans.

**C4. Action items** ([spec](capabilities/05-action-items.md))
Owner, description, due date, confidence, source span. Distinguishes a real
commitment ("I'll have it by Friday") from a hypothetical ("someone should
probably..."). Low-confidence items surface for confirmation rather than
silently dropping.

**C5. Mind maps** ([spec](capabilities/04-mind-maps.md))
A hierarchical map of how the discussion actually branched — not a topic list.
Rendered as Mermaid so it is diffable, embeddable, and editable as text.

### Phase 3 — Leverage

**C6. Chat with transcripts** ([spec](capabilities/06-transcript-chat.md))
Conversational retrieval scoped to one meeting, a meeting series, or the entire
corpus. Chunked with speaker and timestamp metadata so "what did Priya commit to
in Q2 planning" resolves correctly. Always cites; refuses to answer from outside
the corpus.

**C7. Consulting-grade slides** ([spec](capabilities/07-consulting-slides.md))
Structured decks in McKinsey / KPMG / Deloitte house idioms: action titles, MECE
decomposition, pyramid-principle flow, governing thought up front. Outputs .pptx
plus a reviewable structural outline. The structure is generated and reviewed
*before* any rendering happens — a beautiful deck with an incoherent argument is
worse than useless.

### Phase 4 — Development

**C8. Executive coach** ([spec](capabilities/08-executive-coach.md))
Four tracks — written English, spoken English, thought leadership, thought
development — each with an explicit rubric, longitudinal scoring, targeted drills,
and evidence drawn from the user's real transcripts and writing. Coaching is
specific and cites the moment: "in Tuesday's review you hedged the recommendation
three times in ninety seconds; here is the version that lands."

## 6. Key product decisions

**Drive as system of record, not a backup target.** The folder tree is designed to
be navigated by a human with no software. If the app dies, the archive stands alone.
See [ADR-0002](adr/0002-drive-as-system-of-record.md).

**Citations are mandatory, not decorative.** The failure mode that kills trust in
meeting AI is a confident, wrong summary. Every generated claim carries a span
reference the user can click into. Ungrounded claims are dropped, not hedged.
See [ADR-0004](adr/0004-grounded-generation.md).

**Manual override always wins.** Speaker tags, action item owners, and summary
edits made by the user are authoritative and are never overwritten by a later
model run. Corrections are training signal.

**Consent is explicit.** Speaker enrollment requires an affirmative record of
consent per person. The system stores who consented and when.
See [SECURITY_PRIVACY.md](SECURITY_PRIVACY.md).

**Stub-first.** Every external dependency has a working stub. The full system runs,
and the full test suite passes, with zero credentials. This keeps development fast
and makes the architecture honest about its seams.

## 7. Success metrics

**Adoption**
- Recordings processed per week (target: ≥ 80% of meetings recorded)
- Share of recordings whose artifacts are opened at least once post-meeting

**Quality**
- Speaker identification accuracy on a held-out labelled set
- Action-item precision / recall against user-confirmed ground truth
- Summary citation validity — every cited span actually contains the claim
- Deck edit distance: how much the user changes before using it

**Development**
- Rubric scores per track over a 90-day rolling window
- Drill completion rate
- Self-reported confidence in high-stakes communication (quarterly)

## 8. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Recording others without consent | Legal, relational | Explicit consent ledger; jurisdiction guidance in docs; enrollment gate |
| Hallucinated commitments | Loss of trust, wrong action taken | Mandatory span citations; confidence thresholds; low-confidence items require confirmation |
| Diarization fails on poor audio | Whole understanding layer degrades | Quality gate on ingest; graceful degradation to unattributed transcript; always allow manual tagging |
| Cost of LLM over a large corpus | Unsustainable running cost | Model routing (cheap model for extraction, strong model for synthesis); aggressive caching; incremental processing |
| Coaching feels generic or preachy | Feature abandoned | Every point cites a real moment from the user's own recordings; no advice without evidence |
| Drive API quota / large files | Export stalls | Resumable uploads, exponential backoff, manifest-driven resume |
| Scope collapse under ambition | Nothing ships | Strict phase gates; Phase 1 must be boring and complete before Phase 2 starts |

## 9. Open questions

1. **Meeting series identity.** How does the system know Tuesday's standup is the
   same series as last Tuesday's? Calendar integration, title heuristics, or manual
   grouping? *Leaning: manual grouping in v1, heuristics later.*
2. **Voiceprint portability.** If a colleague enrolls, do they own their voiceprint?
   What is the deletion path? *Needs a policy before Phase 2 ships.*
3. **Slide house styles.** How closely should generated decks mimic named firms'
   visual identity? Structural idioms are clearly fine; trade-dress imitation is not.
   *Leaning: adopt the reasoning structures and generic professional styling, not
   firm logos, exact palettes, or branded templates.*
4. **Coach cadence.** Push weekly, or pull on demand? *Leaning: weekly digest plus
   on-demand deep dives.*
5. **Retention.** How long is raw audio kept once artifacts are derived? *Needs a
   default; leaning 12 months with user-configurable override.*
