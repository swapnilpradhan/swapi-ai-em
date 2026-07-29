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
    try:
        turns = await registry.diarization.diarize(meeting)
        meeting.turns = await registry.identification.identify(turns, library)
        meeting = apply_turns_to_transcript(meeting)
        meeting.status.diarization = _ok()
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
