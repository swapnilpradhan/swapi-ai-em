---
name: meeting-summary
description: Produce grounded meeting summaries at three altitudes (one-line, executive paragraph, full brief) plus decisions, risks, open questions, and disagreements — every element citing transcript spans. Use this skill whenever the user asks to summarize, recap, brief, or digest a meeting or transcript, wants key takeaways or decisions from a recording, or is working on summarization prompts and quality. Also use it when reviewing why a summary read as generic, missed a decision, or asserted something the transcript does not support.
---

# Meeting summaries and insights

Read [`docs/capabilities/03-summaries-and-insights.md`](../../../docs/capabilities/03-summaries-and-insights.md)
and [ADR-0004](../../../docs/adr/0004-grounded-generation.md).

## What this is competing against

Not other summarizers — the user re-reading the transcript. That sets the bar: the
summary has to be trustworthy enough that they *don't* go check. One confident wrong
claim resets that trust to zero and the feature is dead, because a summary you have to
verify has saved you nothing.

Everything below follows from that.

## Grounding is structural, not a prompt instruction

Every element is `Cited[T]` carrying `list[TranscriptSpan]`. An uncited claim is not
representable in the type system.

Generation is two-pass, deliberately:

```
1. CHUNK       transcript → overlapping windows with speaker metadata
2. EXTRACT     fast tier, per chunk → candidate claims + spans
3. VALIDATE    mechanical → quote must appear in referenced segments; drop failures
4. SYNTHESIZE  reasoning tier → altitudes + structure, from validated claims ONLY
5. VALIDATE    mechanical → re-check spans on synthesized output
```

The synthesizer never sees raw transcript. It cannot introduce ungrounded material
because it has no ungrounded material to draw from. This is the whole trick.

**Failed validation drops the claim.** Not flagged, not hedged, not shown with a warning
icon — removed. A shorter summary that is entirely true beats a complete summary that is
mostly true. Flagging pushes verification back onto the user, which is the work the
product exists to eliminate.

## The distinction that separates good from generic

**A decision requires an explicit commitment marker.** "We'll go with X", "let's do Y",
"agreed". Discussion that converged without anyone actually deciding is an
`open_question`, not a decision. This is the most common failure in meeting AI: rooms
that talked around a topic get written up as having settled it, and someone acts on a
decision that was never made.

Similarly, `disagreements` is a separate output from `decisions` on purpose. Where the
room did *not* converge is often the most valuable content in the meeting, and the
default behavior of any summarizer is to smooth it into false consensus. Record the
positions and who held them; do not adjudicate.

## Quality rules

1. **Lead with the outcome.** Never narrate chronologically. "The team discussed X, then
   moved to Y" is a table of contents.
2. **Attribute positions.** "Priya argued for deferring; Marcus wanted to proceed" beats
   "the timeline was discussed". Attribution is most of the value.
3. **State absence explicitly.** "No decision on the budget" is information. Silently
   omitting the topic implies it never came up.
4. **No filler.** If a sentence would survive being applied to any meeting, delete it.
   "The meeting covered several important topics" is noise wearing a summary costume.
5. **Match the register.** Working notes for one person, not a press release.

## Altitudes

| Altitude | Budget | Purpose |
|----------|--------|---------|
| one-line | ≤ 20 words | List view. What this meeting *was*. |
| executive | ≤ 120 words, 1 para | Busy reader. Leads with outcome. |
| full brief | ≤ 800 words | Topic-by-topic, positions attributed, discussion shape preserved |

## Practical

- `prompt_version` is part of the cache key. Bumping it invalidates cleanly and
  reprocesses rather than serving stale output — so bump it whenever you change a prompt.
- `MeetingInsights` is partial by design. `section_status` records per-section outcome;
  one section failing must not lose the others.
- Fast tier extracts, reasoning tier synthesizes. Target under $0.15 for a 60-minute
  meeting. Cost discipline is a Phase 2 requirement, not a later optimization.
- Unattributed transcripts still produce usable summaries — just without attribution.

## Checklist

- [ ] 100% of claims carry spans that pass validation
- [ ] Decisions distinguished from converged-but-undecided discussion
- [ ] Disagreements preserved, not smoothed
- [ ] A meeting with no decisions produces a summary saying so
- [ ] Available < 90s after ingest for a 60-minute meeting
- [ ] No sentence that would apply to any meeting
- [ ] One failing section does not lose the others
