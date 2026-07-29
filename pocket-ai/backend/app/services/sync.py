"""The single ingest path.

Webhooks and backfill both land here. That is deliberate: one code path means a
recording pulled by a hook and one pulled by a history sync are processed identically,
and there is exactly one place where dedupe and error handling live.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..core.logging import get_logger
from ..models import Meeting
from .ingest import build_meeting_from_pocket
from .pipeline import process
from .pocket import PocketAuthError, PocketNotFound

log = get_logger(__name__)


class IngestOutcome(str, Enum):
    PROCESSED = "processed"
    ALREADY_CURRENT = "already_current"
    NOT_FOUND = "not_found"
    NO_TRANSCRIPT = "no_transcript"
    FAILED = "failed"


@dataclass
class IngestResult:
    outcome: IngestOutcome
    recording_id: str
    meeting_id: str | None = None
    reason: str | None = None


async def ingest_recording(
    recording_id: str,
    registry,
    store,
    *,
    force: bool = False,
) -> IngestResult:
    """Fetch a recording from Pocket and run it through the pipeline.

    Idempotent by design — webhook delivery is at-least-once, so this gets called
    repeatedly for the same recording and must converge rather than duplicate.
    """
    try:
        recording = await registry.pocket.get_recording(recording_id)
    except PocketNotFound:
        log.info("sync.not_found", recording_id=recording_id)
        return IngestResult(IngestOutcome.NOT_FOUND, recording_id)
    except PocketAuthError as exc:
        # Not retryable, and silence here means the user never learns their key broke.
        log.error("sync.auth_failed", recording_id=recording_id, error=str(exc))
        return IngestResult(IngestOutcome.FAILED, recording_id, reason=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.warning("sync.fetch_failed", recording_id=recording_id, error=str(exc))
        return IngestResult(IngestOutcome.FAILED, recording_id, reason=str(exc))

    if not recording.segments:
        # Common and benign: a `recording.completed` hook can beat transcription.
        # A later transcript event will bring us back here.
        log.info("sync.no_transcript_yet", recording_id=recording_id)
        return IngestResult(IngestOutcome.NO_TRANSCRIPT, recording_id)

    if not force and store.is_current("pocket", recording_id, recording.updated_at):
        existing = store.get_by_external("pocket", recording_id)
        log.debug("sync.already_current", recording_id=recording_id)
        return IngestResult(
            IngestOutcome.ALREADY_CURRENT,
            recording_id,
            meeting_id=existing.id if existing else None,
        )

    audio: bytes | None = None
    try:
        audio = await registry.pocket.download_audio(recording)
    except Exception as exc:  # noqa: BLE001
        # Audio is valuable but not required — the transcript alone still produces
        # every text artifact. Losing the meeting over a failed download would be worse.
        log.warning("sync.audio_failed", recording_id=recording_id, error=str(exc))

    meeting = build_meeting_from_pocket(recording, audio_bytes=audio)
    meeting = _preserve_manual_edits(meeting, store)

    meeting, insights = await process(meeting, registry, library=store.library)
    store.put_meeting(meeting)
    if insights is not None:
        store.put_insights(insights)

    log.info(
        "sync.processed",
        recording_id=recording_id,
        meeting_id=meeting.id,
        diarization=meeting.status.diarization.status.value,
    )
    return IngestResult(IngestOutcome.PROCESSED, recording_id, meeting_id=meeting.id)


def _preserve_manual_edits(meeting: Meeting, store) -> Meeting:
    """Carry the user's manual speaker tags across a re-sync.

    An upstream edit re-fetches the whole transcript, which would otherwise silently
    discard corrections the user made. Manual tags are authoritative and permanent —
    losing them is one of the fastest ways to make someone stop trusting the system.
    """
    existing = (
        store.get_by_external("pocket", meeting.external_ref.external_id)
        if (meeting.external_ref)
        else None
    )
    if existing is None:
        return meeting

    manual = {
        seg.index: (seg.speaker_id, seg.speaker_source)
        for seg in existing.transcript.segments
        if seg.speaker_source is not None and seg.speaker_id
    }
    if not manual:
        return meeting

    from ..models import SpeakerSource

    restored = [
        seg.model_copy(
            update={"speaker_id": manual[seg.index][0], "speaker_source": SpeakerSource.MANUAL}
        )
        if seg.index in manual and manual[seg.index][1] is SpeakerSource.MANUAL
        else seg
        for seg in meeting.transcript.segments
    ]
    meeting.transcript = meeting.transcript.model_copy(update={"segments": restored})
    log.info("sync.preserved_manual_tags", meeting_id=meeting.id, count=len(manual))
    return meeting


async def backfill(
    registry,
    store,
    *,
    limit: int = 50,
    max_recordings: int = 500,
) -> list[IngestResult]:
    """Walk the recording history through the same path as webhooks.

    Bounded by ``max_recordings`` so a first run against a large archive cannot become
    an unbounded job that exhausts API quota in one go.
    """
    results: list[IngestResult] = []
    cursor: str | None = None

    while len(results) < max_recordings:
        page, cursor = await registry.pocket.list_recordings(limit=limit, cursor=cursor)
        if not page:
            break

        for recording in page:
            results.append(await ingest_recording(recording.recording_id, registry, store))
            if len(results) >= max_recordings:
                break

        if not cursor:
            break

    log.info("sync.backfill_complete", count=len(results))
    return results
