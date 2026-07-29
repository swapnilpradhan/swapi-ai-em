"""Ingest: Pocket output → a ``Meeting``.

Two paths land here:

1. **API** (primary) — ``build_meeting_from_pocket``. Structured segments pulled from
   the Pocket API after a webhook, already carrying timings and often speaker labels.
2. **File import** (fallback) — ``build_meeting`` + ``parse_transcript``. A hand-exported
   text transcript. Kept for recordings predating API access and for other devices.

Meeting identity is the audio content hash, so the same recording arriving twice is a
no-op rather than a duplicate. When audio is unavailable we hash the canonical
transcript instead, which is stable across re-fetches of unchanged content.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from ..core.logging import get_logger
from ..models import (
    AudioQuality,
    AudioRef,
    ExternalRef,
    Meeting,
    MeetingSource,
    Transcript,
    TranscriptSegment,
    TranscriptSource,
)
from .pocket import PocketRecording

log = get_logger(__name__)

# Text-export transcript lines: "[00:01:23] text" or "00:01:23 text".
# Only used by the file-import path — the API returns numeric timings.
_TIMESTAMP_LINE = re.compile(r"^\[?(\d{1,2}):(\d{2}):(\d{2})\]?\s*(.*)$")


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_transcript(raw: str) -> Transcript:
    """Parse a Pocket.ai raw transcript into segments.

    Timestamps are treated as relative offsets, not absolute times — Pocket.ai's
    timestamps drift on long recordings, so anything needing precision must re-anchor
    against the audio.
    """
    segments: list[TranscriptSegment] = []
    index = 0

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        match = _TIMESTAMP_LINE.match(line)
        if match:
            h, m, s, text = match.groups()
            start_ms = (int(h) * 3600 + int(m) * 60 + int(s)) * 1000
            text = text.strip()
        else:
            # Untimed line: continues from where the previous one ended.
            start_ms = segments[-1].end_ms if segments else 0
            text = line

        if not text:
            continue

        # Provisional end; corrected below once the next start is known.
        segments.append(
            TranscriptSegment(index=index, start_ms=start_ms, end_ms=start_ms + 1, text=text)
        )
        index += 1

    # Each segment runs until the next one begins.
    fixed: list[TranscriptSegment] = []
    for i, seg in enumerate(segments):
        end = segments[i + 1].start_ms if i + 1 < len(segments) else seg.start_ms + 3000
        fixed.append(seg.model_copy(update={"end_ms": max(end, seg.start_ms + 1)}))

    return Transcript(segments=fixed)


def build_meeting(
    *,
    title: str,
    occurred_at: datetime,
    audio_bytes: bytes,
    raw_transcript: str,
    duration_seconds: float,
    original_filename: str = "audio.m4a",
    quality: AudioQuality | None = None,
    series_id: str | None = None,
) -> Meeting:
    digest = content_hash(audio_bytes)
    transcript = parse_transcript(raw_transcript)

    meeting = Meeting(
        id=digest,
        title=title,
        occurred_at=occurred_at,
        duration_seconds=duration_seconds,
        series_id=series_id,
        source=MeetingSource.POCKET_AI,
        audio=AudioRef(
            content_hash=digest,
            duration_seconds=duration_seconds,
            original_filename=original_filename,
            quality=quality or AudioQuality(),
        ),
        transcript=transcript,
    )
    log.info("ingest.built", meeting_id=meeting.id, segments=len(transcript.segments))
    return meeting


def canonical_transcript_hash(recording: PocketRecording) -> str:
    """Stable hash of transcript content, for when audio is unavailable.

    Namespaced by the upstream recording id, because without audio the transcript is
    all we have and two genuinely different recordings can carry identical text — a
    short standup, a repeated stock phrase. Collapsing those into one meeting would
    silently drop one of them from the external-ref index.

    Within a single recording id the hash still depends only on transcript content, so
    re-fetching unchanged content converges on the same meeting and an unrelated
    metadata change upstream does not mint a new one.
    """
    canonical = json.dumps(
        {
            "recording_id": recording.recording_id,
            "segments": [
                {"t": s.text, "s": s.start_ms, "e": s.end_ms, "sp": s.speaker}
                for s in recording.segments
            ],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return content_hash(canonical.encode("utf-8"))


def transcript_from_pocket(recording: PocketRecording) -> Transcript:
    """Map Pocket's structured segments onto our transcript model.

    Timings arrive as numbers, so there is no parsing and no drift correction — that
    was only ever needed for the text-export path.

    ``speaker`` becomes ``speaker_label``, not ``speaker_id``: upstream tells us
    *which voice*, not *which person*. Identification resolves labels to people
    against the voiceprint library, and until it runs the segment is unattributed.
    """
    segments = [
        TranscriptSegment(
            index=i,
            start_ms=seg.start_ms,
            end_ms=max(seg.end_ms, seg.start_ms + 1),
            text=seg.text,
            speaker_label=seg.speaker,
        )
        for i, seg in enumerate(recording.segments)
    ]
    return Transcript(segments=segments, source=TranscriptSource.POCKET_API)


def build_meeting_from_pocket(
    recording: PocketRecording,
    *,
    audio_bytes: bytes | None = None,
    quality: AudioQuality | None = None,
    series_id: str | None = None,
) -> Meeting:
    """Build a ``Meeting`` from an API-fetched recording.

    Identity prefers the audio hash so a recording imported by file and pulled by API
    resolves to one meeting. Without audio we fall back to the transcript hash, which
    is stable across re-fetches of unchanged content — so webhook redelivery converges
    on the same id rather than duplicating.
    """
    digest = content_hash(audio_bytes) if audio_bytes else canonical_transcript_hash(recording)
    transcript = transcript_from_pocket(recording)

    meeting = Meeting(
        id=digest,
        title=recording.title,
        occurred_at=recording.occurred_at,
        duration_seconds=recording.duration_seconds,
        series_id=series_id,
        source=MeetingSource.POCKET_AI,
        external_ref=ExternalRef(
            provider="pocket",
            external_id=recording.recording_id,
            updated_at=recording.updated_at,
            fetched_at=datetime.now(recording.occurred_at.tzinfo),
        ),
        tags=list(recording.tags),
        audio=AudioRef(
            content_hash=digest,
            duration_seconds=recording.duration_seconds,
            original_filename="audio.m4a",
            quality=quality or AudioQuality(),
        ),
        transcript=transcript,
    )
    log.info(
        "ingest.from_pocket",
        meeting_id=meeting.id,
        segments=len(transcript.segments),
        has_speaker_labels=transcript.has_speaker_labels,
        has_audio=audio_bytes is not None,
    )
    return meeting
