# C3 — Summaries and insights

**Phase:** 2 · **Skill:** `.claude/skills/meeting-summary` · **Service:** `backend/app/services/insights.py`

## Intent

Replace re-reading the transcript. Three altitudes, because "summarize this meeting"
means different things depending on whether you have five seconds, thirty seconds, or
five minutes.

Every element is cited per [ADR-0004](../adr/0004-grounded-generation.md). No exceptions.

## Outputs

### Three altitudes

**One-line** (≤ 20 words). What this meeting was, for a list view.
> "Agreed to defer the Kafka migration to Q4; Priya owns the risk assessment."

**Executive summary** (1 paragraph, ≤ 120 words). What a busy person needs.
Leads with the outcome, not the agenda. If nothing was decided, says so plainly —
"no decision reached" is a valid and useful summary.

**Full brief** (structured, ≤ 800 words). Topic-by-topic, with positions attributed.
Preserves the shape of the discussion including where it went sideways.

### Structured elements

**Decisions.** What was actually decided, who decided it, what it commits the team to.
A decision requires a commitment marker in the transcript — "we'll go with X",
"let's do Y". Discussion that converged without an explicit decision is an
`open_question`, not a decision. This distinction matters enormously and is the most
common place generic summarizers get it wrong.

**Risks.** Concerns raised, with severity where stated. Attributed — knowing *who*
raised a concern is often the point.

**Open questions.** Things explicitly parked, unanswered, or needing follow-up.

**Disagreements.** Where the room did *not* converge. Called out separately and
deliberately: this is frequently the most valuable content in a meeting, and generic
summarizers smooth it into false consensus. Records the positions and who held them,
without adjudicating.

## Generation pipeline

Two-pass, per ADR-0004:

```
1. CHUNK        transcript → overlapping windows with speaker metadata
2. EXTRACT      fast tier, per chunk → candidate claims, each with spans
3. VALIDATE     mechanical → quote must appear in referenced segments; drop failures
4. SYNTHESIZE   reasoning tier → altitudes + structured elements, from validated claims only
5. VALIDATE     mechanical → re-check spans on synthesized output
```

The synthesizer never sees raw transcript — only validated claims. It structurally
cannot introduce ungrounded material.

`prompt_version` is part of the cache key. Improving a prompt invalidates cleanly and
triggers reprocessing rather than serving stale output.

## Quality rules

These are the difference between a summary that gets used and one that gets ignored:

1. **Lead with the outcome.** Never narrate chronologically. "The team discussed X,
   then moved to Y" is a table of contents, not a summary.
2. **Attribute positions.** "Priya argued for deferring; Marcus wanted to proceed" beats
   "the timeline was discussed".
3. **Preserve disagreement.** Do not average conflicting views into a consensus that
   did not happen.
4. **State absence explicitly.** "No decision on the budget" is information. Omitting
   the topic implies it never came up.
5. **No filler.** No "the meeting covered several important topics". If a sentence
   would survive being applied to any meeting, delete it.
6. **Match the register.** These are working notes for one person, not a press release.

## Interface

```python
class InsightsService(Protocol):
    async def summarize(self, meeting: Meeting, *, altitudes: set[Altitude]) -> MeetingInsights: ...
    async def extract_structured(self, meeting: Meeting) -> MeetingInsights: ...
```

`MeetingInsights` is partial by design — `section_status` records per-section success,
so one failing section does not lose the others.

## Acceptance criteria

- [ ] 100% of claims carry spans that pass validation
- [ ] Available < 90s after transcript ingest for a 60-minute meeting
- [ ] Decisions are distinguished from converged-but-undecided discussion
- [ ] Disagreements are preserved, not smoothed
- [ ] A meeting where nothing was decided produces a summary that says so
- [ ] Unattributed transcripts still produce usable summaries (without attribution)
- [ ] Re-running with an unchanged `prompt_version` serves cache; bumping it regenerates
- [ ] One failing section does not lose the others

## Cost control

- Fast tier for extraction (the high-volume pass), reasoning tier for synthesis only.
- Chunk overlap tuned to the minimum that preserves cross-boundary context.
- Cache on `(meeting_id, prompt_version)`.
- Target: under $0.15 for a 60-minute meeting at current pricing. Track actuals from
  Phase 2 onward — cost discipline is a requirement, not a later optimization.
