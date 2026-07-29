# ADR-0007: Coaching is evidence-first or it is not shipped

**Status:** Accepted · **Date:** 2026-07-29

## Context

Executive communication coaching is a crowded space, and almost all of it is generic:
"be more concise", "use the active voice", "lead with the recommendation". The advice
is not wrong. It is useless, because the recipient already knows it and cannot see
where they violate it.

The one thing this system has that no coach or course does is **hundreds of hours of
the user's actual high-stakes communication**, timestamped and searchable. That is
the entire differentiator. A coaching feature that does not exploit it is worse than
no feature — it adds noise and trains the user to ignore the product.

There is also a second failure mode: coaching that is specific but preachy. Nobody
returns to a tool that lectures them weekly.

## Decision

**No coaching output without evidence from the user's own material.**

1. **Every observation cites a real moment.** Not "you tend to hedge" but "in the
   2026-07-14 architecture review, when challenged on the migration timeline, you
   used three hedges in ninety seconds — *[span]* — and the recommendation did not land."
   If a rubric dimension has no supporting evidence in the corpus, it is not scored
   this cycle. Silence is better than invention.

2. **Rubrics are explicit and published.** The four tracks — written English, spoken
   English, thought leadership, thought development — each have named dimensions
   documented in the capability spec. The user can see exactly what is being measured.
   Hidden rubrics produce scores nobody trusts or can act on.

3. **Scores are per-dimension with attached evidence, never a single number.**
   "7/10 communication" is unactionable. "Recommendation clarity: strong. Handling
   challenge: weak, 4 instances this month" is a plan.

4. **One strength and one growth edge per cycle.** Not a list of twelve failings.
   The constraint is deliberate — the goal is behavior change, and behavior change
   comes from focused iteration, not comprehensive audit.

5. **Drills are situational, drawn from the user's real recurring contexts.** If the
   growth edge is handling challenge, the drill uses an actual challenge they faced,
   with a target response — not an invented scenario.

6. **Longitudinal comparison over absolute scoring.** The question is "is this
   improving", not "how good is this". Same-situation before/after comparison is the
   strongest signal available and is only possible because of the corpus.

7. **Tone: observational, not corrective.** Report what happened and what the effect
   was. The user is an adult who can draw conclusions; the system's job is to make
   visible what is otherwise invisible to them.

## Consequences

**Good**
- Coaching that is impossible to get anywhere else. This is the moat.
- Every claim is verifiable — the user can listen to the clip.
- Genuinely measurable progress via same-situation comparison.
- The evidence requirement prevents the drift into generic advice that kills
  these features.

**Bad**
- Coverage gaps: dimensions with no corpus evidence go unscored, so early
  assessments are partial. Accepted — partial and true beats complete and invented.
- Cold start: needs a meaningful corpus before it is useful. Baseline assessment
  requires enough material to be representative.
- Written-track coaching needs a document ingestion path, which is extra surface area.
- Confronting. Hearing yourself hedge is uncomfortable. Tone matters enormously here,
  and getting it wrong causes abandonment.

**Neutral**
- Ties the coach tightly to the transcript corpus, which means it cannot ship before
  Phase 2 identification works. That sequencing is correct anyway.

## Alternatives considered

**Generic rubric-based coaching from a course library.** Ships in a week and adds
nothing that a book does not.

**Score-only dashboards.** Cheap to build, easy to game, and unactionable.

**Real-time in-meeting nudges.** Different product with a different risk profile, and
the evidence for its effectiveness is weak. Explicitly deferred.

**Comprehensive audit of every dimension every cycle.** Rejected — overwhelming, and
it produces a report the user skims once and never revisits.
