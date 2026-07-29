"""Meetings, audio references, and transcripts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .common import StageStatus, TranscriptSpan


class MeetingSource(str, Enum):
    POCKET_AI = "pocket_ai"
    MANUAL_UPLOAD = "manual_upload"


class TranscriptSource(str, Enum):
    POCKET_API = "pocket_api"  # structured segments pulled from the Pocket API
    POCKET_AI_RAW = "pocket_ai_raw"  # text export parsed by hand
    REDIARIZED = "rediarized"
    MANUALLY_CORRECTED = "manually_corrected"


class ExternalRef(BaseModel):
    """Where a meeting came from in the upstream system.

    This is the cheap dedupe key. A webhook redelivery names a recording id, and we
    need to decide "already have it" before spending an audio download on computing
    the content hash. Provenance also matters for re-sync: ``updated_at`` tells us
    whether the upstream copy has moved on.
    """

    model_config = ConfigDict(frozen=True)

    provider: str = "pocket"
    external_id: str
    updated_at: datetime | None = None
    fetched_at: datetime | None = None

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.external_id}"


class SpeakerSource(str, Enum):
    """How a turn got its speaker label.

    ``MANUAL`` is authoritative: identification skips these turns, permanently.
    """

    MODEL = "model"
    MANUAL = "manual"


class AudioQuality(BaseModel):
    """Captured at ingest; gates diarization.

    Diarizing audio that was never going to work burns GPU minutes to produce
    confidently wrong turns, which is worse than declining to attribute at all.
    """

    model_config = ConfigDict(frozen=True)

    snr_db: float | None = None
    clipping_ratio: float = 0.0
    silence_ratio: float = 0.0

    def is_diarizable(self, *, min_snr_db: float = 10.0, max_clipping: float = 0.05) -> bool:
        if self.clipping_ratio > max_clipping:
            return False
        if self.snr_db is not None and self.snr_db < min_snr_db:
            return False
        return True


class AudioRef(BaseModel):
    """A pointer to audio, never the bytes.

    ``content_hash`` is the idempotency anchor for the entire pipeline.
    """

    model_config = ConfigDict(frozen=True)

    content_hash: str
    duration_seconds: float
    sample_rate: int = 16_000
    original_filename: str = "audio.m4a"
    local_path: Path | None = None
    drive_file_id: str | None = None
    quality: AudioQuality = Field(default_factory=AudioQuality)


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    start_ms: int
    end_ms: int
    text: str
    speaker_id: str | None = None
    speaker_label: str | None = None  # "Speaker 2" before identification resolves it
    speaker_source: SpeakerSource | None = None


class Transcript(BaseModel):
    segments: list[TranscriptSegment] = Field(default_factory=list)
    source: TranscriptSource = TranscriptSource.POCKET_AI_RAW

    @property
    def is_attributed(self) -> bool:
        """Whether segments are tied to *named* speakers in our roster."""
        return any(s.speaker_id is not None for s in self.segments)

    @property
    def has_speaker_labels(self) -> bool:
        """Whether the source already separated voices, even if unnamed.

        Pocket returns an optional ``speaker`` per segment. When it is present the
        expensive half of the work — deciding where one voice stops and the next
        begins — is already done, and only identification (label → named person)
        remains. See docs/adr/0008-webhook-driven-ingest.md.
        """
        return any(s.speaker_label for s in self.segments)

    def text_for_span(self, span: TranscriptSpan) -> str:
        window = [s for s in self.segments if span.segment_start <= s.index <= span.segment_end]
        return " ".join(s.text for s in window)


class SpeakerTurn(BaseModel):
    """A contiguous stretch of one voice, from diarization.

    Anonymous (``speaker_id is None``, ``label`` set) until identification runs.
    """

    model_config = ConfigDict(frozen=True)

    start_ms: int
    end_ms: int
    label: str
    speaker_id: str | None = None
    confidence: float | None = None
    source: SpeakerSource = SpeakerSource.MODEL

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class Participant(BaseModel):
    model_config = ConfigDict(frozen=True)

    speaker_id: str | None = None
    display_name: str
    speaking_seconds: float = 0.0


class ProcessingStatus(BaseModel):
    """Per-stage state. Stages fail independently."""

    ingest: StageStatus = Field(default_factory=StageStatus)
    export: StageStatus = Field(default_factory=StageStatus)
    diarization: StageStatus = Field(default_factory=StageStatus)
    identification: StageStatus = Field(default_factory=StageStatus)
    enrichment: StageStatus = Field(default_factory=StageStatus)
    indexing: StageStatus = Field(default_factory=StageStatus)


class Meeting(BaseModel):
    id: str
    title: str
    occurred_at: datetime
    duration_seconds: float
    audio: AudioRef
    transcript: Transcript = Field(default_factory=Transcript)
    series_id: str | None = None
    source: MeetingSource = MeetingSource.POCKET_AI
    # None means this arrived by file import rather than from the upstream API.
    external_ref: ExternalRef | None = None
    tags: list[str] = Field(default_factory=list)
    participants: list[Participant] = Field(default_factory=list)
    turns: list[SpeakerTurn] = Field(default_factory=list)
    status: ProcessingStatus = Field(default_factory=ProcessingStatus)

    @property
    def folder_name(self) -> str:
        """Drive folder name: ``YYYY-MM-DD — Title``.

        Strips path separators and control characters, collapses whitespace, and caps
        the title at 120 chars. See docs/capabilities/01-drive-export.md.
        """
        cleaned = "".join(c for c in self.title if c.isprintable() and c not in "/\\")
        cleaned = " ".join(cleaned.split())[:120].strip() or "Untitled"
        return f"{self.occurred_at:%Y-%m-%d} — {cleaned}"
