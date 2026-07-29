---
name: speaker-identification
description: Diarize meeting audio into speaker turns and identify who each speaker is using an enrolled voiceprint library, with manual tagging that always overrides the model. Use this skill whenever the user mentions speakers, diarization, voiceprints, speaker enrollment, "who said what", attribution, tagging speakers, or unattributed transcripts — and also when debugging wrong speaker labels, conflated voices, or consent and biometric-data handling for meeting participants.
---

# Speaker diarization and identification

Read [`docs/capabilities/02-speaker-identification.md`](../../../docs/capabilities/02-speaker-identification.md)
and [ADR-0003](../../../docs/adr/0003-diarization-separate-from-identification.md).

## These are two problems, not one

This is the thing to internalize before writing any code here:

- **Diarization** — "there are three distinct voices, here are their turns." Depends only
  on the audio. Expensive (minutes of GPU per hour). Its correct output never changes.
- **Identification** — "voice 2 is Priya." Depends on the voiceprint library. Cheap.
  Its correct output *changes over time* as the library grows and the user corrects labels.

Coupling them means every new enrollment forces a full re-diarization, which makes
retroactive naming prohibitively expensive — and retroactive naming is the property that
makes the voiceprint library compound in value.

```python
diarize(audio)              -> turns        key: audio_hash
identify(turns, library)    -> named turns  key: (audio_hash, library_version)
```

Getting `library_version` propagation right is what makes "enroll a colleague today, and
they become named in ten past meetings" work. If you are tempted to simplify the cache
keys, that feature is what you are deleting.

## Rules that matter

**A wrong name is much worse than no name.** Below the similarity threshold, leave the
turn as `Unknown Speaker N`. Users forgive "I don't know who this is"; they do not forgive
a transcript that confidently attributes a commitment to the wrong person. When tuning
the threshold, bias toward precision.

**Manual tags are authoritative, permanently.** A user correction sets
`speaker_source: manual`, and identification skips those turns forever after. Corrections
also feed the voiceprint library — the user is doing labelling work, so capture the value.

**Quality-gate before diarizing.** Check `AudioRef.quality` — SNR, clipping ratio. Bad
audio produces confidently wrong turns after burning GPU minutes, which is worse than
refusing. Fail the stage with a stated reason and let the pipeline continue.

**Degrade, never block.** If diarization fails, the transcript stays unattributed and
everything downstream still runs. Summaries work; they just cannot attribute. Action
items fall back to `owner_raw`. Manual tagging remains available. An audio problem must
never cost the user the whole meeting.

**Consent is structural.** `Speaker.consent` is a required field — a voiceprint cannot be
enrolled without a `ConsentRecord`. `ConsentScope` separates `recording_only` from
`recording_and_voiceprint`, because agreeing to be recorded is not agreeing to a stored
biometric identifier. Default to the narrower reading. If you are adding an enrollment
path that bypasses this, you are building the thing the data model was shaped to prevent.

Revocation must actually work: delete the voiceprint and embeddings, revert that speaker's
turns to anonymous across all meetings, leave a tombstone for auditability.

## Implementation notes

- Backend: pyannote 3.x `speaker-diarization-3.1`, local. Audio never leaves the user's
  infrastructure — that is much of why the heavy dependency is worth it.
- Merge same-speaker turns separated by < 500ms; drop turns < 300ms (backchannel
  "mm-hm" fragments that pollute attribution).
- Pocket.ai transcript timestamps drift on long recordings. Re-anchor to the audio;
  never treat transcript time as absolute.
- Enrollment wants 3+ samples per speaker for robustness across mic conditions.
- pyannote needs `HUGGINGFACE_TOKEN` *and* license acceptance on the HF model page. A
  missing license acceptance fails with an opaque 401 — check that first when it breaks.

## Checklist

- [ ] ≥95% turn accuracy on a labelled set with 3 samples enrolled
- [ ] Unknown speakers stay anonymous rather than being force-matched
- [ ] New enrollment retroactively names past meetings without re-diarizing
- [ ] Manual tags survive re-identification
- [ ] Enrollment without a consent record is rejected
- [ ] Revocation removes the voiceprint and reverts attribution everywhere
- [ ] Poor audio is refused with a reason; the pipeline continues
- [ ] Similar-sounding speakers are not silently conflated
