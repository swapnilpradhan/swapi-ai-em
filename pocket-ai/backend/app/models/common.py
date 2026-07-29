"""Shared value objects.

``TranscriptSpan`` and ``Cited`` are the load-bearing types in this codebase. Every
generated claim carries spans, and validation checks that the quoted text actually
appears in the referenced segments. See docs/adr/0004-grounded-generation.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ModelTier(str, Enum):
    """Which model to route a task to.

    Routing is config, not code: a capability declares the tier it needs and the
    registry resolves it to a concrete model id.
    """

    FAST = "fast"
    REASONING = "reasoning"


class TranscriptSpan(BaseModel):
    """A citation into a transcript.

    ``quote`` is stored redundantly (it is derivable from the segment range) so that
    citations survive a re-diarization that renumbers segments, and so validation
    does not require loading the full transcript.
    """

    model_config = ConfigDict(frozen=True)

    meeting_id: str
    segment_start: int = Field(ge=0)
    segment_end: int = Field(ge=0)
    quote: str

    def overlaps(self, other: TranscriptSpan) -> bool:
        if self.meeting_id != other.meeting_id:
            return False
        return self.segment_start <= other.segment_end and other.segment_start <= self.segment_end


class Cited(BaseModel, Generic[T]):
    """A value together with the evidence supporting it.

    Making citation part of the type rather than a convention means an uncited claim
    is a construction error rather than something to catch in review.
    """

    model_config = ConfigDict(frozen=True)

    value: T
    spans: list[TranscriptSpan] = Field(min_length=1)


class SectionStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_RUN = "not_run"


class StageStatus(BaseModel):
    """Per-stage processing state.

    Stages fail independently — "diarization failed but summarization succeeded" is a
    real and useful state, which is why this is a per-stage record rather than one
    enum on the meeting.
    """

    model_config = ConfigDict(frozen=True)

    status: SectionStatus = SectionStatus.NOT_RUN
    reason: str | None = None
    completed_at: datetime | None = None


class DateRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: datetime
    end: datetime
