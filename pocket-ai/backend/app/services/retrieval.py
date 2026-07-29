"""Corpus indexing, retrieval, and grounded chat.

Retrieval is hybrid: metadata filters (speaker, date, series) plus semantic search.
Running "what did Priya commit to" as pure vector similarity returns chunks about
commitments by anyone — confidently and wrongly.

See docs/capabilities/06-transcript-chat.md.
"""

from __future__ import annotations

from ..core.config import Settings
from ..core.logging import get_logger
from ..models import (
    AnswerStatus,
    Chunk,
    Citation,
    CitedAnswer,
    Filters,
    Meeting,
    Scope,
)
from .protocols import LLMService

log = get_logger(__name__)

CHUNK_TARGET_CHARS = 1600  # ~400 tokens
CONTEXT_CHARS = 400  # ~100 tokens carried from the previous chunk


def chunk_meeting(meeting: Meeting) -> list[Chunk]:
    """Split a transcript into retrieval units on speaker-turn boundaries.

    Never splits mid-turn: a chunk cutting through a sentence loses the claim it
    contained, unrecoverably at query time. Each chunk carries the tail of its
    predecessor so a chunk opening with "yeah, exactly" is resolvable.
    """
    chunks: list[Chunk] = []
    buffer: list[str] = []
    speakers: set[str] = set()
    start_index = 0
    previous_tail = ""

    def flush(end_index: int) -> None:
        nonlocal buffer, speakers, previous_tail, start_index
        if not buffer:
            return
        text = " ".join(buffer)
        chunks.append(
            Chunk(
                id=f"{meeting.id}:{start_index}-{end_index}",
                text=text,
                meeting_id=meeting.id,
                meeting_title=meeting.title,
                occurred_at=meeting.occurred_at,
                series_id=meeting.series_id,
                speakers=sorted(speakers),
                segment_range=(start_index, end_index),
                preceding_context=previous_tail,
            )
        )
        previous_tail = text[-CONTEXT_CHARS:]
        buffer = []
        speakers = set()
        start_index = end_index + 1

    for seg in meeting.transcript.segments:
        buffer.append(seg.text)
        if seg.speaker_label:
            speakers.add(seg.speaker_label)
        if seg.speaker_id:
            speakers.add(seg.speaker_id)
        if sum(len(t) for t in buffer) >= CHUNK_TARGET_CHARS:
            flush(seg.index)

    if meeting.transcript.segments:
        flush(meeting.transcript.segments[-1].index)

    return chunks


def apply_filters(chunks: list[Chunk], filters: Filters) -> list[Chunk]:
    """Metadata filtering — the half of retrieval that vector search cannot do."""
    result = chunks
    if filters.meeting_id:
        result = [c for c in result if c.meeting_id == filters.meeting_id]
    if filters.series_id:
        result = [c for c in result if c.series_id == filters.series_id]
    if filters.speakers:
        wanted = set(filters.speakers)
        result = [c for c in result if wanted & set(c.speakers)]
    if filters.after:
        result = [c for c in result if c.occurred_at >= filters.after]
    if filters.before:
        result = [c for c in result if c.occurred_at <= filters.before]
    return result


class StubRetrievalService:
    """In-memory index with keyword scoring.

    No embeddings, but the filter-then-search shape is identical to the real thing,
    so chunking, filtering, and citation construction are all exercised offline.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._chunks: dict[str, list[Chunk]] = {}

    async def index(self, meeting: Meeting) -> int:
        chunks = chunk_meeting(meeting)
        self._chunks[meeting.id] = chunks  # incremental: only this meeting is touched
        log.info("index.stub", meeting_id=meeting.id, chunks=len(chunks))
        return len(chunks)

    def _all_chunks(self) -> list[Chunk]:
        return [c for chunks in self._chunks.values() for c in chunks]

    async def search(
        self, query: str, *, scope: Scope, filters: Filters, k: int = 12
    ) -> list[Chunk]:
        candidates = apply_filters(self._all_chunks(), filters)
        terms = {t for t in query.lower().split() if len(t) > 2}
        if not terms:
            return candidates[:k]

        scored = [(sum(1 for t in terms if t in c.text.lower()), c) for c in candidates]
        hits = [c for score, c in sorted(scored, key=lambda p: -p[0]) if score > 0]
        return hits[:k]


class ChromaRetrievalService:
    """Real vector index. Requires the ``rag`` extra. Phase 3."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def index(self, meeting: Meeting) -> int:
        raise NotImplementedError("Phase 3 — see docs/capabilities/06-transcript-chat.md")

    async def search(
        self, query: str, *, scope: Scope, filters: Filters, k: int = 12
    ) -> list[Chunk]:
        raise NotImplementedError("Phase 3 — see docs/capabilities/06-transcript-chat.md")


class GroundedChatService:
    """Answers from retrieved chunks only, or refuses.

    The refusal path is the feature. "I don't find any discussion of that in your
    meetings" is correct and useful; one confident answer drawn from general knowledge
    destroys the premise that these answers come from the user's own corpus.
    """

    def __init__(self, settings: Settings, retrieval, llm: LLMService) -> None:
        self.settings = settings
        self.retrieval = retrieval
        self.llm = llm

    async def ask(self, question: str, *, scope: Scope, filters: Filters) -> CitedAnswer:
        chunks = await self.retrieval.search(question, scope=scope, filters=filters)

        if not chunks:
            # "Nothing matched" and "you narrowed the search" send the user in
            # opposite directions, so they are distinct statuses.
            narrow = filters.is_narrow
            return CitedAnswer(
                question=question,
                status=(AnswerStatus.FILTERS_TOO_NARROW if narrow else AnswerStatus.NOT_IN_CORPUS),
                answer=(
                    "No matching discussion found within the filters applied. "
                    "Widening the speaker or date range may help."
                    if narrow
                    else "I don't find any discussion of that in your meetings."
                ),
                scope=scope,
            )

        citations = [
            Citation(
                meeting_id=c.meeting_id,
                meeting_title=c.meeting_title,
                occurred_at=c.occurred_at,
                span=c.to_span(),
            )
            for c in chunks[:5]
        ]

        titles = ", ".join(sorted({c.meeting_title for c in chunks[:5]}))
        answer = (
            f"[stub] Found {len(chunks)} relevant passages across: {titles}. "
            "Configure ANTHROPIC_API_KEY for a synthesized answer."
        )

        return CitedAnswer(
            question=question,
            status=AnswerStatus.ANSWERED,
            answer=answer,
            citations=citations,
            scope=scope,
        )
