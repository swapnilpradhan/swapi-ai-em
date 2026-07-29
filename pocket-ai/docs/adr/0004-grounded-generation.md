# ADR-0004: Every generated claim must cite a transcript span

**Status:** Accepted · **Date:** 2026-07-29

## Context

The failure mode that kills meeting-AI products is not a missing feature. It is a
confident, plausible, wrong summary. Once a user catches the system asserting that
someone committed to a deadline they never mentioned, every subsequent output is
suspect — and the product's entire value proposition (trusting it so you do not have
to re-read the transcript) collapses.

This risk is worse here than in general chat, because the outputs drive action.
A hallucinated action item gets assigned to a real person.

Prompt-level mitigations ("only use information from the transcript") reduce the rate
but do not eliminate it, and they give no way to *detect* when it happened.

## Decision

**Citation is a type-level requirement, not a prompt instruction.**

1. Every generated claim is wrapped in `Cited[T]`, which carries
   `list[TranscriptSpan]`. There is no code path that produces an uncited summary
   bullet, action item, mind map node, or coaching observation — it is not
   representable in the model.

2. **A validation pass runs after every generation.** For each span, the quoted text
   must actually appear in the referenced transcript segments (normalized for
   whitespace and casing). Fuzzy match with a high threshold, to tolerate minor
   transcription reformatting.

3. **Claims that fail validation are dropped, not softened.** Not flagged, not
   hedged, not shown with a warning icon. Removed. A shorter summary that is entirely
   true beats a complete summary that is mostly true, because the second one requires
   the user to verify everything, which is the work we were supposed to eliminate.

4. **The UI surfaces citations.** Every claim is clickable through to the moment in
   the transcript. This is not a nice-to-have — it is what converts "trust the system"
   into "verify in two seconds", which is a much more robust foundation for trust.

5. **Generation is two-pass where needed.** Fast tier extracts candidate claims with
   spans; reasoning tier synthesizes only from validated claims. The synthesizer never
   sees raw transcript, so it cannot introduce ungrounded material.

## Consequences

**Good**
- Hallucination becomes detectable and automatically suppressed rather than a thing
  users discover the hard way.
- Verification cost for the user drops to near zero.
- Prompt regressions are caught by validation-failure rate as a metric.
- Forces honesty about coverage — if the system cannot cite it, it does not know it.

**Bad**
- Summaries are sometimes shorter or more fragmented than an ungrounded generator
  would produce. Accepted deliberately.
- Genuinely valid *inferences* across the whole meeting ("the team is misaligned on
  priorities") are hard to cite to a single span and may be dropped. Partially
  mitigated by allowing multi-span citations for synthesis claims.
- Real implementation and latency cost in the validation pass.
- Two-pass generation costs more tokens than one pass.

**Neutral**
- Constrains prompt design significantly. Prompts must request spans in structured
  output, which rules out free-form generation.

## Alternatives considered

**Prompt-only grounding.** Cheap, standard, and it fails silently. Rejected — no
detection mechanism.

**Confidence scores instead of citations.** Self-reported LLM confidence is poorly
calibrated and, more importantly, a low-confidence wrong answer still shows up in
the summary.

**Flag unvalidated claims instead of dropping them.** Rejected: it pushes verification
back onto the user for every flagged item, which is the exact work the product exists
to remove. A flag is an admission that we do not know, wrapped in an interface that
implies we do.

**Post-hoc fact-checking with a second model.** More expensive than span validation and
less reliable — it substitutes one model's judgment for a mechanical check against
ground truth.
