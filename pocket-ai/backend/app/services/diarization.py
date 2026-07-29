"""Diarization and speaker identification — two stages, two caches.

See docs/adr/0003-diarization-separate-from-identification.md.
"""

from __future__ import annotations

from ..core.config import Settings
from ..core.logging import get_logger
from ..models import Meeting, SpeakerSource, SpeakerTurn, VoiceprintLibrary

log = get_logger(__name__)

# Turns shorter than this are usually backchannel ("mm-hm") and pollute attribution.
MIN_TURN_MS = 300
# Same-speaker turns closer than this are one turn interrupted by a pause.
MERGE_GAP_MS = 500


def merge_turns(turns: list[SpeakerTurn]) -> list[SpeakerTurn]:
    """Merge adjacent same-speaker turns and drop backchannel fragments."""
    if not turns:
        return []

    ordered = sorted(turns, key=lambda t: t.start_ms)
    merged: list[SpeakerTurn] = [ordered[0]]

    for turn in ordered[1:]:
        last = merged[-1]
        same_speaker = turn.label == last.label
        close_enough = turn.start_ms - last.end_ms <= MERGE_GAP_MS
        if same_speaker and close_enough:
            merged[-1] = last.model_copy(update={"end_ms": max(last.end_ms, turn.end_ms)})
        else:
            merged.append(turn)

    return [t for t in merged if t.duration_ms >= MIN_TURN_MS]


class DiarizationRefused(RuntimeError):
    """Raised when audio quality makes diarization pointless.

    Refusing is better than producing confidently wrong turns after burning GPU
    minutes — the caller degrades to an unattributed transcript.
    """


class StubDiarizationService:
    """Derives plausible turns from transcript structure.

    Produces structurally valid output so every downstream stage is exercised: turns
    alternate between two labels on segment boundaries, which is enough to test
    merging, alignment, and identification without any audio processing.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def diarize(self, meeting: Meeting) -> list[SpeakerTurn]:
        if not meeting.audio.quality.is_diarizable(
            min_snr_db=self.settings.min_snr_db,
            max_clipping=self.settings.max_clipping_ratio,
        ):
            raise DiarizationRefused(
                f"audio quality below threshold (snr={meeting.audio.quality.snr_db}, "
                f"clipping={meeting.audio.quality.clipping_ratio})"
            )

        turns = [
            SpeakerTurn(
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                label=f"Speaker {(i % 2) + 1}",
                confidence=0.5,
            )
            for i, seg in enumerate(meeting.transcript.segments)
        ]
        merged = merge_turns(turns)
        log.info("diarize.stub", meeting_id=meeting.id, turns=len(merged))
        return merged


class PyannoteDiarizationService:
    """Real diarization via pyannote 3.x, running locally.

    Audio never leaves the user's infrastructure, which is much of why the heavy
    dependency is worth taking. Lands in Phase 2; requires the ``audio`` extra,
    ``HUGGINGFACE_TOKEN``, and license acceptance on the HF model page.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def diarize(self, meeting: Meeting) -> list[SpeakerTurn]:
        raise NotImplementedError("Phase 2 — see docs/capabilities/02-speaker-identification.md")


class StubIdentificationService:
    """Assigns enrolled speakers to anonymous clusters, in order.

    Deterministic and offline. Crucially it reproduces the two behaviours that matter:
    manually-tagged turns are never touched, and clusters beyond the enrolled roster
    stay anonymous rather than being force-matched.
    """

    def __init__(self, settings: Settings, threshold: float = 0.7) -> None:
        self.settings = settings
        self.threshold = threshold

    async def identify(
        self, turns: list[SpeakerTurn], library: VoiceprintLibrary
    ) -> list[SpeakerTurn]:
        enrolled = library.enrolled()
        if not enrolled:
            return turns

        labels = sorted({t.label for t in turns if t.source is not SpeakerSource.MANUAL})
        assignment = {label: enrolled[i].id for i, label in enumerate(labels) if i < len(enrolled)}

        identified = []
        for turn in turns:
            # A manual tag is the user's own correction. It outranks any model output,
            # permanently — see docs/capabilities/02-speaker-identification.md.
            if turn.source is SpeakerSource.MANUAL:
                identified.append(turn)
                continue
            speaker_id = assignment.get(turn.label)
            if speaker_id is None:
                # Better anonymous than wrong: an unmatched cluster keeps its label.
                identified.append(turn)
                continue
            identified.append(turn.model_copy(update={"speaker_id": speaker_id, "confidence": 0.9}))

        log.info("identify.stub", assigned=len(assignment), turns=len(identified))
        return identified


class EmbeddingIdentificationService:
    """Real identification by embedding similarity against the voiceprint library.

    Cache key is ``(audio_hash, library_version)``, so enrolling a new speaker
    retroactively names them in past meetings without re-diarizing. Phase 2.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def identify(
        self, turns: list[SpeakerTurn], library: VoiceprintLibrary
    ) -> list[SpeakerTurn]:
        raise NotImplementedError("Phase 2 — see docs/capabilities/02-speaker-identification.md")
