"""Ingest: raw Pocket.ai output → a ``Meeting``.

Meeting identity is the audio content hash, so re-uploading the same file is a no-op
rather than a duplicate.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime

from ..core.logging import get_logger
from ..models import (
    AudioQuality,
    AudioRef,
    Meeting,
    MeetingSource,
    Transcript,
    TranscriptSegment,
)

log = get_logger(__name__)

# Pocket.ai raw transcript lines: "[00:01:23] text" or "00:01:23 text"
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
