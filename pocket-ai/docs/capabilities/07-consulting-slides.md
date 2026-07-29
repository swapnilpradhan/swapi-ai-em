# C7 — Consulting-grade slides

**Phase:** 3 · **Skill:** `.claude/skills/consulting-slides` · **Service:** `backend/app/agents/slide_builder.py`

See [ADR-0006](../adr/0006-slides-structure-before-render.md) for why structure comes
before rendering.

## Intent

Turn a meeting — or a set of meetings — into a deck that could go in front of a
steering committee. The requirement is "McKinsey / KPMG / Deloitte style", and the
important thing to be clear about is that this is a request about **argument
structure**, not fonts.

## What actually makes a strategy-firm deck work

These are public, well-documented techniques. They are the deliverable:

**Governing thought.** The single assertion the deck exists to prove, stated on the
first content slide. If you cannot write it in one sentence, the deck has no point.

**Pyramid principle** (Minto). Conclusion first, then supporting arguments, then
evidence. Never build up to a reveal — an executive audience reads the first slide and
may read no further, so the answer goes there.

**MECE decomposition.** Supporting arguments are Mutually Exclusive (no overlap) and
Collectively Exhaustive (nothing material missing). Typically 3, sometimes 2–5. More
than 5 means the decomposition is wrong.

**Action titles.** Every slide title is the assertion the slide proves, written as a
full sentence:
- ✅ "Margin compression is concentrated in the enterprise segment"
- ❌ "Margin Analysis"

Reading only the titles, top to bottom, should give the complete argument. This is the
single highest-leverage rule and the one most generators get wrong.

**One message per slide.** The body exists only to prove the title. If the body proves
two things, it is two slides.

**So-what test.** Every slide answers "so what?". A slide that presents data without
an implication is a slide that has not earned its place.

## Pipeline

```
1. Derive governing thought       reasoning tier   → one assertion + spans
2. Build MECE argument tree       reasoning tier   → 2-5 supporting arguments
3. Validate MECE                  mechanical       → overlap + coverage check
4. Write action titles            reasoning tier   → one assertion per slide
5. Select evidence per slide      fast tier        → spans, quotes, data
6. Emit structural outline        mechanical       → reviewable Markdown
   ──────────────── REVIEW GATE ────────────────
7. Render                         python-pptx      → .pptx
```

Steps 1–6 produce a Markdown outline readable in under a minute. Rendering is a
separate call. **The outline is the artifact of record; the .pptx is a projection.**

Step 3 is mechanical where possible: check that supporting arguments do not overlap
in the spans they cite, and that together they cover the governing thought's claim
space. Catching a broken decomposition here is nearly free; catching it after
rendering is not.

## Structural intermediate representation

```python
DeckStructure
├── governing_thought: Cited[str]
├── audience: str                 shapes register and depth
├── arguments: list[Argument]     the MECE decomposition
└── appendix: list[Slide]

Argument
├── assertion: str                becomes a section
├── slides: list[Slide]
└── spans: list[TranscriptSpan]

Slide
├── action_title: str             full-sentence assertion
├── body: SlideBody               bullets | chart | table | quote | comparison
├── so_what: str                  the implication; if empty, the slide is cut
└── spans: list[TranscriptSpan]
```

## House styles

We adopt **structural idioms and generic professional styling**. We do not reproduce
firm logos, proprietary templates, or trade dress — those belong to those firms.

| Style | Structural emphasis | Visual register |
|-------|--------------------|-----------------|
| `mckinsey` | Hypothesis-led; tight MECE; heavy exhibit use; dense action titles | Minimal, high-density, restrained palette |
| `kpmg` | Risk and control framing; assurance language; matrix layouts | Structured, table-forward |
| `deloitte` | Capability/maturity framing; phased roadmaps; implementation orientation | Layered, roadmap-heavy |
| `neutral` | Pyramid principle, no firm-specific framing | Clean default |

The differences that matter are in how the argument is framed, not the color scheme.

## Evidence and citation

Per ADR-0004, every assertion — governing thought, argument, action title — cites
transcript spans. An assertion the corpus cannot support does not become a slide.

This is a hard constraint with a real consequence: the deck can only argue what the
meetings actually establish. That is the correct behavior. A generator that fills gaps
with plausible strategy language produces a deck that collapses in the first question
from the room.

## Rendering

- `python-pptx`, 16:9.
- Title slide, section dividers, content slides, appendix.
- Charts generated from meeting data where the argument needs quantification.
- Speaker notes carry the citations, so the presenter can source any claim live.
- Also emits `deck.md` — the outline — which is often all the user needs.

## Acceptance criteria

- [ ] Reading only the action titles gives the complete argument
- [ ] Governing thought is stated on the first content slide
- [ ] Supporting arguments pass MECE validation
- [ ] Every slide has a non-empty `so_what`
- [ ] Every assertion cites valid spans
- [ ] Outline is reviewable and editable before rendering
- [ ] Editing the outline and re-rendering produces a matching deck
- [ ] Generated deck is usable with < 15 minutes of editing
- [ ] No firm logos or proprietary template assets are reproduced
- [ ] A meeting with no coherent argument produces a clear failure, not a padded deck
