# Skills

One skill per capability. Each skill is the *execution procedure*; the matching spec in
`docs/capabilities/` is the *contract*. When they disagree, the spec wins — update the
skill to match, not the other way round.

| Skill | Capability | Phase | Spec |
|-------|-----------|-------|------|
| `drive-export` | Google Drive export | 1 | [01](../../docs/capabilities/01-drive-export.md) |
| `speaker-identification` | Diarization + speaker ID | 2 | [02](../../docs/capabilities/02-speaker-identification.md) |
| `meeting-summary` | Summaries and insights | 2 | [03](../../docs/capabilities/03-summaries-and-insights.md) |
| `mind-map` | Mind maps | 2 | [04](../../docs/capabilities/04-mind-maps.md) |
| `action-items` | Action item extraction | 2 | [05](../../docs/capabilities/05-action-items.md) |
| `transcript-chat` | Chat with transcripts | 3 | [06](../../docs/capabilities/06-transcript-chat.md) |
| `consulting-slides` | Consulting-grade decks | 3 | [07](../../docs/capabilities/07-consulting-slides.md) |
| `executive-coach` | Executive development | 4 | [08](../../docs/capabilities/08-executive-coach.md) |

## Shared constraints

Three rules cut across every skill. They are repeated in each one because they are the
things most likely to be quietly dropped under delivery pressure:

1. **Cite or drop.** Every generated claim carries `TranscriptSpan` references that pass
   validation. A claim that cannot be cited is removed, not hedged.
   ([ADR-0004](../../docs/adr/0004-grounded-generation.md))
2. **Manual overrides are permanent.** User corrections to speakers, owners, and edits
   are authoritative and are never overwritten by a later model run.
3. **Degrade, never block.** A failing stage must not cost the user the whole meeting.

## Testing these skills

These were authored against the conventions in the `skill-creator` skill but have not
yet been through its eval loop. Before relying on any of them heavily, run:

```
/skill-creator   # then: draft test prompts, run with/without skill, review, iterate
```

The highest-value candidates for evaluation are `meeting-summary`, `action-items`, and
`consulting-slides` — the ones where output quality is subjective and the failure modes
are subtle.
