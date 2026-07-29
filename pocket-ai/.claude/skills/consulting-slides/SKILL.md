---
name: consulting-slides
description: Build strategy-consulting-grade decks from meetings using pyramid principle, MECE decomposition, and action titles — producing a reviewable structural outline before rendering any .pptx. Use this skill whenever the user asks for slides, a deck, a presentation, an exec or board readout, or mentions McKinsey/KPMG/Deloitte/BCG style, action titles, MECE, or pyramid principle. Also use it when a generated deck looked polished but argued poorly, or when working on deck structure, storylining, or slide rendering.
---

# Consulting-grade slides

Read [`docs/capabilities/07-consulting-slides.md`](../../../docs/capabilities/07-consulting-slides.md)
and [ADR-0006](../../../docs/adr/0006-slides-structure-before-render.md).

## Read the request correctly

"McKinsey style" sounds like a request about fonts. It is not. What makes a strategy-firm
deck effective is **argument architecture**, and that is the deliverable. A beautiful deck
with a rambling argument is worse than a text document, because the polish hides the
incoherence until someone asks a question in the room.

So: structure first, always. Rendering is the easy part and it comes last.

## The techniques

These are public, well-documented, and they are the actual product.

**Governing thought.** The single assertion the deck exists to prove, on the first content
slide. If it cannot be written in one sentence, the deck has no point yet — stop and find it.

**Pyramid principle** (Minto). Conclusion first, then supporting arguments, then evidence.
Never build to a reveal. An executive reads slide one and may read no further, so the
answer goes there.

**MECE.** Supporting arguments are Mutually Exclusive and Collectively Exhaustive.
Typically 3, sometimes 2–5. More than 5 means the decomposition is wrong, not that the
topic is complex.

**Action titles.** Every title is the assertion the slide proves, as a full sentence.

- ✅ "Margin compression is concentrated in the enterprise segment"
- ❌ "Margin Analysis"

**Reading only the titles, top to bottom, must give the complete argument.** This is the
highest-leverage rule and the one most generators get wrong. Test it explicitly: extract
the titles into a list and read them. If they do not form a coherent argument, the deck
does not either.

**One message per slide.** The body exists only to prove the title. If the body proves
two things, it is two slides.

**So-what test.** Every slide answers "so what?". A slide presenting data with no
implication has not earned its place — cut it.

## Pipeline

```
1. Derive governing thought    reasoning tier   → one assertion + spans
2. Build MECE argument tree    reasoning tier   → 2-5 supporting arguments
3. Validate MECE               mechanical       → overlap + coverage check
4. Write action titles         reasoning tier   → one assertion per slide
5. Select evidence per slide   fast tier        → spans, quotes, data
6. Emit structural outline     mechanical       → reviewable Markdown
   ─────────── REVIEW GATE ───────────
7. Render                      python-pptx      → .pptx
```

**The outline is the artifact of record; the .pptx is a projection of it.** Restructuring
costs one Markdown regeneration instead of a re-render. Often the outline is all the user
needs.

Step 3 is mechanical where it can be: check that supporting arguments do not overlap in
the spans they cite, and that together they cover the governing thought's claim space.
Catching a broken decomposition here is nearly free.

## Honesty constraint

Every assertion cites transcript spans (ADR-0004). An assertion the corpus cannot support
does not become a slide.

This has a real consequence worth stating plainly: **the deck can only argue what the
meetings actually establish.** If that produces a thin deck, the honest output is a thin
deck plus a note about what evidence is missing. Filling gaps with plausible strategy
language produces something that collapses at the first question — which is precisely the
situation this is meant to prevent.

## House styles

Adopt **structural idioms plus generic professional styling**. Do not reproduce firm
logos, proprietary templates, or trade dress — those belong to those firms, and a deck
that imitates them misrepresents its origin.

| Style | Structural emphasis |
|-------|--------------------|
| `mckinsey` | Hypothesis-led, tight MECE, heavy exhibit use, dense action titles |
| `kpmg` | Risk and control framing, assurance language, matrix layouts |
| `deloitte` | Capability/maturity framing, phased roadmaps, implementation orientation |
| `neutral` | Pyramid principle, no firm-specific framing |

The differences that matter are in how the argument is framed, not the palette.

## Rendering

- `python-pptx`, 16:9. Title slide, section dividers, content, appendix.
- Charts where the argument needs quantification — not for decoration.
- **Speaker notes carry the citations**, so the presenter can source any claim live.
  This is a small detail that makes the deck genuinely defensible in a room.
- Also emit `deck.md` — the outline.

## Checklist

- [ ] Titles alone give the complete argument
- [ ] Governing thought on the first content slide
- [ ] Arguments pass MECE validation
- [ ] Every slide has a non-empty `so_what`
- [ ] Every assertion cites valid spans
- [ ] Outline reviewable and editable before render
- [ ] Edited outline re-renders to a matching deck
- [ ] No firm logos or proprietary template assets
- [ ] A meeting with no coherent argument fails clearly rather than padding
