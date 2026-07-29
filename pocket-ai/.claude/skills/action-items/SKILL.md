---
name: action-items
description: Extract real commitments from meeting transcripts with owner, due date, confidence, and commitment type — distinguishing firm commitments from hypotheticals so the list stays trustworthy. Use this skill whenever the user mentions action items, to-dos, follow-ups, commitments, next steps, owners, or deadlines from a meeting or recording. Also use it when debugging a task list that feels noisy, has wrong owners, invented deadlines, or lost the user's manual edits after regeneration.
---

# Action item extraction

Read [`docs/capabilities/05-action-items.md`](../../../docs/capabilities/05-action-items.md).

## The failure mode to design against

A to-do list padded with things nobody actually committed to is worse than no list. The
user reads it once, finds three items that were never real commitments, and stops
trusting it — but still has to skim it, so it costs time forever while providing nothing.

Precision beats recall here, decisively. A missed action item is recoverable (it usually
comes up again). A fabricated one erodes the whole feature.

## The core distinction

`commitment_type` is the field that makes this work. These are genuinely different
objects and flattening them destroys the feature:

| Type | Signal | Example | Treatment |
|------|--------|---------|-----------|
| `firm` | First-person commitment with intent | "I'll have the doc by Friday" | Extract, high confidence |
| `assigned` | Directed at a named person, **accepted** | "Priya, can you own this?" → "Yep" | Extract, owner = Priya |
| `soft` | Conditional, tentative, or unaccepted | "I could take a look if there's time" | Extract, flag for confirmation |
| `hypothetical` | Impersonal, no owner, no acceptance | "Someone should probably review this" | **Do not extract** |

The subtle one: directed-but-unaccepted is `soft`, not `assigned`. "Priya, can you own
this?" with no response from Priya is a request, not a commitment. Silence is not
acceptance, and treating it as such assigns work to people who never agreed to it.

## Fields that carry ambiguity forward

**`owner_raw` preserves what was actually said** — "you", "the platform team", "whoever
picks this up". Resolving that to a speaker id and discarding the original loses the
information needed to correct a wrong guess. Keep both.

**`description` must be self-contained.** It is read in a list, far from its source.
"Send it to them" is useless. Rewrite using surrounding context: "Send the migration plan
to the platform team." This is a genuine rewrite, not a quote — the span citation carries
the verbatim source.

**Never invent a date.** Relative dates anchor to `meeting.occurred_at`, never to
processing time — a meeting processed a week late must not shift every deadline.

| Said | Parsed |
|------|--------|
| "by Friday" | next Friday from `occurred_at` |
| "end of quarter" | last day of that quarter |
| "next sprint" | `None`, raw preserved — sprint boundaries are unknown |
| "soon" | `None`, raw preserved |

A guessed date is a false deadline that someone will plan around. `None` plus the raw
text is the honest answer and is more useful than a confident fabrication.

## Confidence handling

- `≥ 0.8` → surfaced directly
- `0.5 – 0.8` → "confirm these" queue
- `< 0.5` → retained in the record, not surfaced

Queue, never silently drop. The user decides what is real.

## Stability across re-runs

The user edits these — assigns owners, marks done, corrects descriptions. Re-summarizing
with a bumped `prompt_version` must not orphan that work. Match item identity on span
overlap plus description similarity, and treat user edits (`confirmed_by_user`, `status`,
corrected owner) as authoritative and never overwritten.

Silently discarding a user's edits is the second-fastest way to kill this feature.

## Owner resolution

1. First person ("I'll") → speaker of the span. Needs attribution; without it, fall back
   to `owner_raw`.
2. Named person → match the meeting roster, then the global speaker list.
3. Second person ("you") → addressee, inferable from the preceding turn. Low confidence,
   flag it.
4. Team or role → no `owner_speaker_id`, keep `owner_raw`.

## Checklist

- [ ] Precision ≥ 0.85 against user-confirmed ground truth
- [ ] Hypotheticals not extracted
- [ ] Directed-but-unaccepted is `soft`, not `assigned`
- [ ] Dates anchor to `occurred_at`
- [ ] Unparseable dates yield `None` + raw, never a guess
- [ ] Descriptions readable out of context
- [ ] User edits survive regeneration
- [ ] Low-confidence items queue rather than disappear
