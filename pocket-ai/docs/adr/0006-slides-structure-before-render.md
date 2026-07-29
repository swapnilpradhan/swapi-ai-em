# ADR-0006: Slide generation produces reviewable structure before rendering

**Status:** Accepted · **Date:** 2026-07-29

## Context

The requirement is "McKinsey / KPMG / Deloitte style" decks. It is easy to read that
as a visual request — the right fonts, a clean grid, a blue palette. It is not. What
makes a strategy-firm deck effective is the *argument architecture*:

- A **governing thought** stated up front — the one thing the deck exists to say.
- **Pyramid principle**: conclusion first, then supporting arguments, then evidence.
- **MECE decomposition**: the supporting arguments are mutually exclusive and
  collectively exhaustive.
- **Action titles**: every slide's title is the assertion the slide proves
  ("Margin compression is concentrated in the enterprise segment"), not a label
  ("Margin Analysis").
- **One message per slide**, with the body existing only to prove the title.

A generator that produces beautiful slides with a rambling argument has produced
something worse than a text document — it has hidden the incoherence behind polish.

The failure mode is also expensive to fix late: once the deck is rendered, restructuring
means redoing everything.

## Decision

**Slide generation is a multi-step pipeline where structure is produced, validated,
and made reviewable before any rendering happens.**

```
1. Derive governing thought        (reasoning tier)  →  single assertion + spans
2. Build MECE argument tree        (reasoning tier)  →  2-5 supporting arguments
3. Validate MECE                   (mechanical)      →  overlap + coverage checks
4. Write action titles             (reasoning tier)  →  one assertion per slide
5. Select evidence per slide       (fast tier)       →  cited spans, charts, quotes
6. Emit structural outline         (mechanical)      →  reviewable Markdown
   ─────────────── review gate ───────────────
7. Render                          (python-pptx)     →  .pptx
```

Steps 1–6 emit a Markdown outline the user can read and edit in under a minute.
Rendering is a separate call. The outline is the artifact of record; the `.pptx` is
a projection of it.

Additional commitments:

- **Every slide carries citations** to transcript spans, per ADR-0004. An assertion
  the corpus cannot support does not become a slide.
- **House styles are structural idioms plus generic professional styling.** We adopt
  the reasoning patterns — action titles, pyramid flow, MECE, the "so what" test —
  and clean, neutral visual design. We do not reproduce firm logos, proprietary
  templates, or trade dress. Those belong to those firms, and a deck that imitates
  them is a misrepresentation waiting to happen.
- **The MECE validation is mechanical where possible.** Checking that supporting
  arguments do not overlap and do collectively cover the governing thought is a
  structural check, not a matter of taste, and catching it before rendering is cheap.

## Consequences

**Good**
- The expensive-to-fix problem (bad argument) surfaces at the cheapest moment.
- The outline is a genuinely useful artifact on its own — often it is all the user needs.
- Restructuring costs one regeneration of a Markdown file, not a re-render.
- Rendering becomes a boring, testable transformation.
- Structure and styling evolve independently.

**Bad**
- More steps, more LLM calls, higher latency and cost than a single-shot generator.
- The review gate is friction. Users who want a deck *now* will find it annoying, so
  an "auto-approve" path is needed for trusted cases.
- Multi-step pipelines have more places to fail.

**Neutral**
- Requires an explicit intermediate representation for deck structure, which is more
  code but also the thing that makes the pipeline testable.

## Alternatives considered

**Single prompt → pptx.** Fast to build. Rejected: no point at which the argument can
be inspected or corrected, and argument quality is the entire deliverable.

**Render first, then critique the rendered deck.** Rejected — critique of a rendered
artifact tends toward cosmetic feedback, and fixing structure at that point is expensive.

**Template-filling from a fixed deck skeleton.** Predictable output, but forces every
meeting into one narrative shape. Real arguments have different shapes; the structure
should follow the content.

**Mimic firm templates exactly.** Rejected on both legal and ethical grounds. The
structural idioms are public knowledge and genuinely valuable; the trade dress is
neither ours nor necessary.
