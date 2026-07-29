"""The processing pipeline.

Stages are checkpointed rather than streamed, and each one is independently
re-runnable. A failing stage degrades the result; it never costs the user the whole
meeting. See docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..core.logging import get_logger
from ..models import (
    Meeting,
    MeetingInsights,
    SectionStatus,
    SpeakerSource,
    SpeakerTurn,
    StageStatus,
    TranscriptSegment,
    VoiceprintLibrary,
)
from .artifacts import build_artifacts
from .diarization import DiarizationRefused
from .registry import ServiceRegistry

log = get_logger(__name__)


def _ok() -> StageStatus:
    return StageStatus(status=SectionStatus.OK, completed_at=datetime.now(UTC))


def _failed(reason: str) -> StageStatus:
    return StageStatus(status=SectionStatus.FAILED, reason=reason, completed_at=datetime.now(UTC))


def _skipped(reason: str) -> StageStatus:
    """Not run because it wasn't needed — distinct from failure, and a good outcome."""
    return StageStatus(status=SectionStatus.SKIPPED, reason=reason, completed_at=datetime.now(UTC))


def turns_from_transcript_labels(meeting: Meeting) -> list[SpeakerTurn]:
    """Derive speaker turns from labels the source already provided.

    Consecutive segments sharing a label collapse into one turn, which is the same
    shape diarization would have produced — so identification and everything
    downstream cannot tell the difference.
    """
    turns: list[SpeakerTurn] = []

    for seg in meeting.transcript.segments:
        if not seg.speaker_label:
            continue
        if turns and turns[-1].label == seg.speaker_label:
            turns[-1] = turns[-1].model_copy(update={"end_ms": max(turns[-1].end_ms, seg.end_ms)})
        else:
            turns.append(
                SpeakerTurn(
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    label=seg.speaker_label,
                    # Upstream is authoritative about *where the voice changed*; our
                    # own model had no say, so confidence is theirs, not ours.
                    confidence=None,
                )
            )

    return turns


def apply_turns_to_transcript(meeting: Meeting) -> Meeting:
    """Attribute transcript segments from speaker turns by timestamp overlap.

    Manually-tagged segments are left alone — a user correction outranks any model
    output, permanently.
    """
    if not meeting.turns:
        return meeting

    updated: list[TranscriptSegment] = []
    for seg in meeting.transcript.segments:
        if seg.speaker_source is SpeakerSource.MANUAL:
            updated.append(seg)
            continue

        best = max(
            meeting.turns,
            key=lambda t: min(t.end_ms, seg.end_ms) - max(t.start_ms, seg.start_ms),
            default=None,
        )
        if best is None:
            updated.append(seg)
            continue

        overlap = min(best.end_ms, seg.end_ms) - max(best.start_ms, seg.start_ms)
        if overlap <= 0:
            updated.append(seg)
            continue

        updated.append(
            seg.model_copy(
                update={
                    "speaker_id": best.speaker_id,
                    "speaker_label": best.label,
                    "speaker_source": SpeakerSource.MODEL,
                }
            )
        )

    meeting.transcript = meeting.transcript.model_copy(update={"segments": updated})
    return meeting


async def process(
    meeting: Meeting,
    registry: ServiceRegistry,
    *,
    library: VoiceprintLibrary | None = None,
) -> tuple[Meeting, MeetingInsights | None]:
    """Run the full pipeline, degrading rather than failing.

    Export runs immediately after ingest so raw material is safe before any later
    stage can fail, and again after enrichment so derived artifacts land alongside
    their source.
    """
    library = library or VoiceprintLibrary()
    meeting.status.ingest = _ok()

    # Raw material first — this is the stage that must never be skipped.
    try:
        await registry.storage.export_all(meeting, build_artifacts(meeting))
        meeting.status.export = _ok()
    except Exception as exc:  # noqa: BLE001 - export failure must not stop processing
        log.warning("pipeline.export_failed", meeting_id=meeting.id, error=str(exc))
        meeting.status.export = _failed(str(exc))

    # Diarization and identification: failure here costs attribution, nothing else.
    #
    # When the source already separated voices — Pocket returns an optional `speaker`
    # per segment — the expensive half is done and we skip straight to identification.
    # Splitting these two stages (ADR-0003) is what makes that short-circuit possible.
    try:
        if meeting.transcript.has_speaker_labels:
            turns = turns_from_transcript_labels(meeting)
            meeting.status.diarization = _skipped("source provided speaker labels")
        else:
            turns = await registry.diarization.diarize(meeting)
            meeting.status.diarization = _ok()

        meeting.turns = await registry.identification.identify(turns, library)
        meeting = apply_turns_to_transcript(meeting)
        meeting.status.identification = _ok()
    except DiarizationRefused as exc:
        log.info("pipeline.diarization_refused", meeting_id=meeting.id, reason=str(exc))
        meeting.status.diarization = _failed(str(exc))
    except Exception as exc:  # noqa: BLE001
        log.warning("pipeline.diarization_failed", meeting_id=meeting.id, error=str(exc))
        meeting.status.diarization = _failed(str(exc))

    insights: MeetingInsights | None = None
    try:
        insights = await registry.insights.enrich(meeting)
        meeting.status.enrichment = _ok()
    except Exception as exc:  # noqa: BLE001
        log.warning("pipeline.enrichment_failed", meeting_id=meeting.id, error=str(exc))
        meeting.status.enrichment = _failed(str(exc))

    # Derived artifacts alongside their source.
    if insights is not None:
        try:
            await registry.storage.export_all(meeting, build_artifacts(meeting, insights))
        except Exception as exc:  # noqa: BLE001
            log.warning("pipeline.reexport_failed", meeting_id=meeting.id, error=str(exc))

    try:
        await registry.retrieval.index(meeting)
        meeting.status.indexing = _ok()
    except Exception as exc:  # noqa: BLE001
        log.warning("pipeline.indexing_failed", meeting_id=meeting.id, error=str(exc))
        meeting.status.indexing = _failed(str(exc))

    return meeting, insights
