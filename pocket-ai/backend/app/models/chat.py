"""Retrieval and chat over the transcript corpus."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .common import TranscriptSpan


class Scope(str, Enum):
    """Always explicit, never inferred.

    Inferring scope wrongly produces answers that are right about the wrong meeting —
    a failure the user has almost no way to notice.
    """

    MEETING = "meeting"
    SERIES = "series"
    CORPUS = "corpus"


class Chunk(BaseModel):
    """A retrieval unit.

    Split on speaker-turn boundaries, never mid-turn: a chunk cutting through a
    sentence loses the claim it contained, unrecoverably. ``preceding_context`` makes
    a chunk starting "yeah, I agree with that" resolvable.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    text: str
    meeting_id: str
    meeting_title: str
    occurred_at: datetime
    series_id: str | None = None
    speakers: list[str] = Field(default_factory=list)  # structured filter field
    segment_range: tuple[int, int] = (0, 0)
    preceding_context: str = ""

    def to_span(self) -> TranscriptSpan:
        return TranscriptSpan(
            meeting_id=self.meeting_id,
            segment_start=self.segment_range[0],
            segment_end=self.segment_range[1],
            quote=self.text,
        )


class Filters(BaseModel):
    """Metadata filters parsed out of the question.

    "What did Priya commit to in Q2 planning" is a filter plus a search, not a
    similarity guess. Run as pure vector search it returns chunks about commitments
    by anyone — confidently and wrongly.
    """

    model_config = ConfigDict(frozen=True)

    meeting_id: str | None = None
    series_id: str | None = None
    speakers: list[str] = Field(default_factory=list)
    after: datetime | None = None
    before: datetime | None = None

    @property
    def is_narrow(self) -> bool:
        return bool(self.speakers or self.after or self.before or self.series_id)


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    meeting_id: str
    meeting_title: str
    occurred_at: datetime
    span: TranscriptSpan


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    NOT_IN_CORPUS = "not_in_corpus"
    FILTERS_TOO_NARROW = "filters_too_narrow"


class CitedAnswer(BaseModel):
    """An answer grounded in the corpus, or an honest refusal.

    ``NOT_IN_CORPUS`` and ``FILTERS_TOO_NARROW`` are distinct: "we never discussed
    that" and "I only looked at three meetings" send the user in opposite directions.
    """

    model_config = ConfigDict(frozen=True)

    question: str
    status: AnswerStatus
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    scope: Scope = Scope.CORPUS


class ChatTurn(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str  # user | assistant
    content: str
