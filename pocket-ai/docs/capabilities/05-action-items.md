# C5 — Action items

**Phase:** 2 · **Skill:** `.claude/skills/action-items` · **Service:** `backend/app/services/insights.py`

## Intent

Extract what people actually committed to — and, critically, *not* extract what they
didn't. A to-do list padded with hypotheticals is a to-do list nobody trusts, and an
untrusted list is worse than none, because it still costs time to read.

## The core distinction

The single most important field is `commitment_type`. These are different objects and
flattening them destroys the feature:

| Type | Signal | Example | Treatment |
|------|--------|---------|-----------|
| `firm` | Explicit first-person commitment with intent | "I'll have the doc by Friday" | Extract, high confidence |
| `assigned` | Directed at a named person, accepted | "Priya, can you own this?" / "Yep" | Extract, owner = Priya |
| `soft` | Conditional or tentative | "I could take a look if there's time" | Extract, flag for confirmation |
| `hypothetical` | Impersonal, no owner, no acceptance | "Someone should probably review this" | **Do not extract** as an action item |

Directed-but-unaccepted ("Priya, can you own this?" with no response) is `soft`, not
`assigned`. Silence is not acceptance.

## Model

```python
ActionItem
├── id: str
├── description: str            imperative, self-contained, no pronouns
├── owner_speaker_id: str | None resolved against the roster
├── owner_raw: str              what was actually said: "you", "the platform team"
├── due: DueDate | None         parsed + raw
├── confidence: float
├── commitment_type: CommitmentType
├── spans: list[TranscriptSpan]
├── confirmed_by_user: bool
└── status: ActionStatus        open | done | dropped
```

**`owner_raw` is preserved deliberately.** "You should handle that" resolved to a
speaker id loses the information needed to correct a wrong guess. Keeping the raw text
means an ambiguous reference stays correctable instead of silently wrong.

**`description` must be self-contained.** "Send it to them" is useless out of context.
Rewrite to "Send the migration plan to the platform team" using surrounding context —
the description is read in a list, far from its source.

## Date parsing

Relative dates are anchored to `meeting.occurred_at`, never to processing time. A
meeting processed a week late must not shift every deadline.

| Said | Parsed |
|------|--------|
| "by Friday" | next Friday from `occurred_at` |
| "end of quarter" | last day of the quarter containing `occurred_at` |
| "next sprint" | `None` + raw preserved (sprint boundaries are unknown) |
| "soon" / "shortly" | `None` + raw preserved |

Never invent a date. `None` with raw text preserved is correct; a guessed date is a
false deadline that someone will plan around.

## Owner resolution

1. First person ("I'll") → the speaker of the span. Requires attribution; without it,
   fall back to `owner_raw`.
2. Named person → match against the meeting roster, then the global speaker list.
3. Second person ("you") → the addressee, inferable from the immediately preceding turn.
   Low confidence; flag for confirmation.
4. Team or role ("the platform team") → no `owner_speaker_id`, `owner_raw` preserved.

## Confidence and confirmation

- `confidence ≥ 0.8` → surfaced directly.
- `0.5 ≤ confidence < 0.8` → surfaced in a "confirm these" queue.
- `confidence < 0.5` → not surfaced, retained in the record for debugging.

Low-confidence items are queued, never silently dropped. The user decides.

## Stability across re-runs

Re-summarizing must not orphan user edits. Item identity is matched on span overlap
plus description similarity, so an item the user assigned an owner to survives a
regeneration with a bumped `prompt_version`. User edits (`confirmed_by_user`, `status`,
corrected owner) are authoritative and are never overwritten.

## Cross-meeting follow-through

Phase 3. Since action items carry stable ids and meetings link into series, the system
can surface what was promised and never closed — commitments that recur unresolved
across three consecutive meetings are exactly the thing that falls through the cracks
in real organizations.

## Acceptance criteria

- [ ] Precision ≥ 0.85 against user-confirmed ground truth
- [ ] Hypotheticals are not extracted as action items
- [ ] Directed-but-unaccepted requests are `soft`, not `assigned`
- [ ] Relative dates anchor to `occurred_at`, not processing time
- [ ] Unparseable dates yield `None` plus raw text, never a guess
- [ ] Descriptions are self-contained and readable out of context
- [ ] User edits survive re-generation
- [ ] Low-confidence items queue for confirmation rather than disappearing
- [ ] Every item cites valid spans
