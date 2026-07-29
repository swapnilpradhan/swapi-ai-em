# ADR-0003: Diarization and speaker identification are separate stages

**Status:** Accepted · **Date:** 2026-07-29

## Context

"Who said what" looks like one problem. Most off-the-shelf pipelines treat it as one:
feed in audio and enrolled voiceprints, get back a labelled transcript.

It is actually two problems with very different characteristics:

- **Diarization** — segment audio into turns by distinct voice. Expensive (minutes of
  GPU per hour of audio), depends only on the audio, and its output never changes
  unless the audio changes.
- **Identification** — map each anonymous voice to a named person. Cheap (embedding
  comparison), depends on the voiceprint library, and its correct output *changes over
  time* as the library grows and as the user corrects mistakes.

Coupling them means every library change forces a full re-diarization.

## Decision

Two stages, two caches, two idempotency keys.

```
diarize(audio) -> list[SpeakerTurn]                       key: audio_hash
identify(turns, library) -> list[SpeakerTurn]             key: (audio_hash, library_version)
```

Consequences that follow directly:

1. **Enrolling a new speaker retroactively names them everywhere.** When a colleague
   is enrolled today, `library_version` bumps, identification re-runs across affected
   meetings, and they become named in the ten past meetings where they were
   "Speaker 3". No audio is reprocessed.
2. **Manual corrections are authoritative and cheap.** A user correction writes to the
   turn and feeds the library. It never triggers re-diarization.
3. **Diarization can fail independently.** Bad audio yields no turns, and the system
   degrades to an unattributed transcript rather than failing the whole meeting.
   Summaries still work; they just cannot attribute.
4. **The pieces are independently swappable.** Replacing pyannote with a different
   diarizer does not touch identification, and vice versa.

## Consequences

**Good**
- Retroactive naming is close to free — a genuinely valuable property that a coupled
  design cannot offer at all.
- The expensive stage runs exactly once per audio file, ever.
- Clean degradation path.

**Bad**
- Two caches to invalidate correctly. Getting `library_version` propagation wrong
  means stale labels, which is a confusing bug class.
- Slightly more code than a single combined call.
- Re-identification across a large corpus needs to be a background job with
  progress reporting, not a synchronous operation.

## Alternatives considered

**Single combined pipeline.** Simpler and what most libraries hand you. Rejected
because retroactive identification — the property that makes the voiceprint library
compound in value over time — is impossible without re-running the expensive stage.

**Identification only, no diarization** (assign every segment to the closest
voiceprint). Rejected: fails completely on unknown speakers, and segment boundaries
from the raw transcript do not align with speaker turns.

**Manual tagging only.** Rejected as a primary mechanism — it does not scale past a
few meetings. Retained as an always-available override, which is a different and
necessary thing.
