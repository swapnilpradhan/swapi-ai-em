# C2 — Speaker diarization and identification

**Phase:** 2 · **Skill:** `.claude/skills/speaker-identification` · **Service:** `backend/app/services/diarization.py`

See [ADR-0003](../adr/0003-diarization-separate-from-identification.md) for why these
are two stages.

## Intent

Turn "a wall of text" into "Priya said this, you said that". This is the capability
that makes a transcript useful six months later, and everything downstream —
action-item ownership, corpus chat filters, spoken-English coaching — depends on it.

## Two stages

### Stage 1: Diarization

Audio in, anonymous speaker turns out.

```python
async def diarize(self, audio: AudioRef) -> list[SpeakerTurn]
```

- Backend: pyannote 3.x `speaker-diarization-3.1`, running locally. Audio never leaves
  the user's infrastructure — a major reason for accepting the heavy dependency.
- Cache key: `audio_hash`. Runs exactly once per audio file, ever.
- Post-processing: merge adjacent turns from the same speaker separated by < 500ms;
  drop turns shorter than 300ms (usually backchannel "mm-hm" fragments that pollute
  attribution).
- Align turns to transcript segments by timestamp overlap. Pocket.ai timestamps drift
  on long recordings — re-anchor against the audio rather than trusting transcript
  time as absolute.

**Quality gate.** Before diarizing, check `AudioRef.quality`. If SNR is below
threshold or the clipping ratio is high, refuse and mark the stage failed with a
reason. Diarizing unusable audio burns GPU minutes to produce confidently wrong turns,
which is worse than no attribution at all.

### Stage 2: Identification

Anonymous turns plus voiceprint library in, named turns out.

```python
async def identify(self, turns: list[SpeakerTurn], library: VoiceprintLibrary) -> list[SpeakerTurn]
```

- Cache key: `(audio_hash, library_version)`.
- Extract a speaker embedding per anonymous cluster, compare against enrolled
  voiceprints by cosine similarity.
- Assign when similarity exceeds the calibrated threshold; otherwise leave anonymous
  and label `Unknown Speaker N`. A wrong name is much worse than no name.
- **Retroactive naming**: enrolling a new speaker bumps `library_version`, which
  invalidates identification caches and re-runs identification — not diarization —
  across affected meetings. A colleague enrolled today becomes named in the ten past
  meetings where they were "Speaker 3".

## Enrollment

Requires **3+ samples** per speaker for robustness across microphone conditions and
vocal variation.

Enrollment paths:
1. **From a meeting** — user tags an anonymous cluster with a name; those turns become
   enrollment samples.
2. **Direct** — upload a clean audio sample.

**Consent is structurally required.** `Speaker.consent` is a mandatory
`ConsentRecord`; a voiceprint cannot be enrolled without one. `ConsentScope`
distinguishes `recording_only` from `recording_and_voiceprint` — agreeing to be
recorded is not agreeing to a stored biometric identifier, and the system defaults to
the narrower reading. See [SECURITY_PRIVACY.md](../SECURITY_PRIVACY.md).

**Revocation** deletes the voiceprint and all embeddings, reverts that speaker's turns
to anonymous across all meetings, and leaves an auditable tombstone.

## Manual tagging

Always available, always authoritative.

- User corrections write directly to the turn and are never overwritten by a later
  model run — the correction sets `speaker_source: manual`, and identification skips
  manually-tagged turns.
- Corrections feed the voiceprint library as additional samples, so the system gets
  better at the speakers the user actually cares about.
- Bulk operations: "all of Speaker 2 in this meeting is Priya", and "Speaker 2 here is
  the same person as Speaker 4 in last week's meeting".

## Degradation

If diarization fails or is skipped, the transcript stays unattributed and the pipeline
continues. Summaries and mind maps still work; they simply cannot say who said what.
Action-item owners fall back to `owner_raw`. Manual tagging remains available.
Never block the whole meeting on an audio-quality problem.

## Acceptance criteria

- [ ] ≥95% turn accuracy on a held-out labelled set with 3 enrolled samples per speaker
- [ ] Unknown speakers are left anonymous rather than force-matched
- [ ] Enrolling a new speaker retroactively names them in past meetings without re-diarizing
- [ ] Manual tags survive re-identification
- [ ] Voiceprint enrollment without a consent record is rejected
- [ ] Revocation removes the voiceprint and reverts attribution everywhere
- [ ] Poor-quality audio is refused with a clear reason, and the pipeline continues
- [ ] Two speakers with similar voices are not silently conflated

## Open questions

- Threshold calibration: per-user, or global? Per-user is more accurate but needs
  labelled data the user must produce.
- Overlapping speech: pyannote handles it partially. Do we surface overlap explicitly,
  or attribute to the dominant speaker?
- Voiceprint portability and ownership if a colleague wants their data back
  (flagged in the PRD as unresolved).
