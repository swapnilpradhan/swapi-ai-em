# C8 — Executive coach

**Phase:** 4 · **Skill:** `.claude/skills/executive-coach` · **Service:** `backend/app/agents/coach.py`

See [ADR-0007](../adr/0007-coaching-must-cite-evidence.md). The governing constraint:
**no coaching output without evidence from the user's own material.**

## Intent

Use the corpus — hundreds of hours of the user's actual high-stakes communication — to
develop them as an executive communicator. This is the one thing no course, book, or
human coach can do, because none of them were in the room for every meeting.

Four tracks, each with an explicit published rubric.

---

## Track 1 — Written English

**Source:** documents the user ingests — memos, strategy docs, emails, PR descriptions,
Slack messages they choose to submit.

| Dimension | What is measured |
|-----------|------------------|
| Clarity | Sentence-level comprehensibility; ambiguity; unresolved referents |
| Concision | Words per idea; redundancy; throat-clearing openings |
| Structure | Does the document lead with the conclusion? Is it scannable? |
| Precision | Vague quantifiers ("significant", "several") where specifics exist |
| Register | Appropriateness to audience and channel |
| Hedging | Density of qualifiers that weaken a claim without adding accuracy |

---

## Track 2 — Spoken English

**Source:** the user's own turns in the transcript corpus. Timestamps and speaker
attribution make this measurable in a way self-report never is.

| Dimension | What is measured |
|-----------|------------------|
| Airtime | Share of speaking time vs. room; monologue length distribution |
| Filler density | "um", "like", "you know", "sort of" per minute |
| Hedging under pressure | Qualifier density when challenged vs. baseline — the most diagnostic signal here |
| Answer latency & directness | Does the answer come first, or after preamble? |
| Interruption pattern | Interrupts given and received |
| Question quality | Ratio of open/probing to closed/leading questions |
| Landing | Does the recommendation get restated and confirmed, or dissolve? |

**Hedging under pressure is the flagship metric.** It is invisible to the speaker,
highly consequential, and only measurable with a corpus that includes the moments of
challenge. Baseline hedging rate vs. hedging rate in the 60 seconds after a
challenging question is a single number that captures something real.

---

## Track 3 — Thought leadership

**Source:** written output plus the user's substantive contributions in meetings.

| Dimension | What is measured |
|-----------|------------------|
| Point of view | Does the user hold and state positions, or synthesize others'? |
| Distinctiveness | Would this claim survive being said by anyone else in the field? |
| Evidence | Are positions backed by data, experience, or assertion? |
| Consistency | Does the position hold across contexts, or shift with audience? |
| Reach | Does the position get adopted, cited, or referenced by others? |
| Framing | Does the user name and define concepts others then use? |

`Reach` is measurable from the corpus: if the user coins a framing in March and three
colleagues use it by June, that is thought leadership with evidence.

---

## Track 4 — Thought development

The hardest and most valuable track: not *how* ideas are expressed but how they are
*formed*.

| Dimension | What is measured |
|-----------|------------------|
| Argument structure | Are claims supported, or asserted and elaborated? |
| Steelmanning | Does the user engage the strongest counter-argument, or the weakest? |
| Updating | Does the position change on new evidence? Recorded when it happens |
| Abstraction control | Can the user move between principle and specific deliberately? |
| First-principles reasoning | Analogy and precedent, or derivation from fundamentals? |
| Idea maturity | Tracked over time: which positions are sharpening, which are stalling |

**Idea maturity tracking** is unique to a longitudinal corpus. A position first
voiced tentatively in January, refined through five discussions, and stated crisply
in June has a visible trajectory. So does one repeated verbatim for a year without
development — which is the more useful finding.

---

## Assessment cycle

```
1. Collect     new transcripts (spoken tracks) + submitted documents (written)
2. Score       per dimension, evidence required — no evidence, no score
3. Compare     against rolling 90-day baseline
4. Select      ONE strength + ONE growth edge
5. Drill       generate a targeted exercise from a real situation
6. Deliver     weekly digest; deep dives on demand
```

**One strength, one growth edge.** Not a list of twelve failings. Behavior change comes
from focused iteration; comprehensive audits get skimmed once and abandoned.

**Unscored dimensions are stated as unscored.** If the corpus has no evidence of
handling challenge this month, that dimension is not scored. Inventing a score to fill
the table destroys the credibility of every other score.

## Drills

Situational, built from the user's real recurring contexts:

- **Rewrite** — "here is what you said; here is a version 40% shorter that keeps the
  commitment" (written and spoken).
- **Challenge response** — replays an actual challenging question from a real meeting;
  user drafts a response; compare against what they said and a target version.
- **Steelman** — take the position the user argued against and construct its
  strongest form.
- **Compression** — state a real position from a real meeting in 30 seconds.
- **Same-situation replay** — the strongest measure available: the same recurring
  meeting type, three months apart, scored on the same dimensions.

## Tone

Observational, not corrective. Report what happened and what effect it had. The user
is an adult who can draw their own conclusions; the job is to make visible what is
otherwise invisible.

> "In Tuesday's architecture review, when Marcus challenged the migration timeline,
> you used three hedges in ninety seconds — *'probably', 'I think maybe', 'it could be
> that'* — and the meeting moved on without a decision. In the same discussion two
> weeks earlier, you stated the constraint directly and the room converged in four
> minutes."

Not: "You should be more assertive."

## Interface

```python
class CoachService(Protocol):
    async def assess(self, *, track: CoachingTrack, window: DateRange) -> CoachingAssessment: ...
    async def weekly_digest(self) -> CoachingDigest: ...
    async def deep_dive(self, topic: str) -> CoachingAssessment: ...
    async def generate_drill(self, dimension: str) -> Drill: ...
```

## Acceptance criteria

- [ ] Every observation cites a real span or document reference
- [ ] Dimensions with no evidence are reported unscored, never invented
- [ ] Exactly one strength and one growth edge per weekly digest
- [ ] Drills reference the user's actual situations
- [ ] Same-situation before/after comparison works across a 90-day window
- [ ] Rubrics are published and visible to the user
- [ ] Regression on any dimension triggers an alert
- [ ] Tone is observational — no imperatives, no praise inflation
- [ ] Baseline assessment requires a stated minimum corpus size before it will run

## Open questions

- Minimum corpus size for a valid baseline. Ten meetings? Twenty hours?
- Rubric validity — these dimensions are reasoned from communication literature but are
  not externally validated. Worth grounding against published frameworks before Phase 4.
- Cadence: weekly digest is the default, but is that too often for behavior change on
  a 90-day measurement window?
- Whether the coach should ever see meetings the user marks private.
