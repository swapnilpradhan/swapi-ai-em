"""Chunking, filtering, and the refusal path."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.models import AnswerStatus, Filters, Scope
from backend.app.services.llm import StubLLMService
from backend.app.services.retrieval import (
    GroundedChatService,
    StubRetrievalService,
    apply_filters,
    chunk_meeting,
)


class TestChunking:
    def test_produces_chunks_covering_the_transcript(self, meeting):
        chunks = chunk_meeting(meeting)
        assert chunks
        assert chunks[0].meeting_id == meeting.id
        assert chunks[-1].segment_range[1] == meeting.transcript.segments[-1].index

    def test_empty_transcript_produces_no_chunks(self, meeting):
        empty = meeting.model_copy(
            update={"transcript": meeting.transcript.model_copy(update={"segments": []})}
        )
        assert chunk_meeting(empty) == []

    def test_chunk_converts_to_a_usable_span(self, meeting):
        span = chunk_meeting(meeting)[0].to_span()
        assert span.meeting_id == meeting.id
        assert span.quote


class TestFilters:
    def _chunks(self, meeting):
        return chunk_meeting(meeting)

    def test_speaker_filter_is_a_real_filter(self, meeting):
        """Not a similarity guess — this is the point of hybrid retrieval."""
        chunks = self._chunks(meeting)
        tagged = [c.model_copy(update={"speakers": ["priya"]}) for c in chunks]

        assert apply_filters(tagged, Filters(speakers=["priya"])) == tagged
        assert apply_filters(tagged, Filters(speakers=["marcus"])) == []

    def test_meeting_filter(self, meeting):
        chunks = self._chunks(meeting)
        assert apply_filters(chunks, Filters(meeting_id=meeting.id)) == chunks
        assert apply_filters(chunks, Filters(meeting_id="other")) == []

    def test_date_filters(self, meeting):
        chunks = self._chunks(meeting)
        after = datetime(2027, 1, 1, tzinfo=UTC)
        assert apply_filters(chunks, Filters(after=after)) == []
        assert apply_filters(chunks, Filters(before=after)) == chunks

    def test_is_narrow_detects_restrictive_filters(self):
        assert Filters(speakers=["priya"]).is_narrow
        assert not Filters().is_narrow
        # A meeting id alone is a scope choice, not a narrowing of the search.
        assert not Filters(meeting_id="m1").is_narrow


class TestGroundedChat:
    async def _service(self, settings, meeting):
        retrieval = StubRetrievalService(settings)
        await retrieval.index(meeting)
        return GroundedChatService(settings, retrieval, StubLLMService(settings))

    async def test_answers_from_the_corpus_with_citations(self, settings, meeting):
        service = await self._service(settings, meeting)
        answer = await service.ask("Kafka migration", scope=Scope.CORPUS, filters=Filters())

        assert answer.status is AnswerStatus.ANSWERED
        assert answer.citations
        assert answer.citations[0].meeting_id == meeting.id

    async def test_refuses_rather_than_answering_from_general_knowledge(self, settings, meeting):
        """The single rule that makes this feature trustworthy."""
        service = await self._service(settings, meeting)
        answer = await service.ask(
            "photosynthesis chlorophyll", scope=Scope.CORPUS, filters=Filters()
        )

        assert answer.status is AnswerStatus.NOT_IN_CORPUS
        assert not answer.citations
        assert "don't find" in answer.answer

    async def test_distinguishes_narrow_filters_from_absent_content(self, settings, meeting):
        """'Never discussed' and 'you narrowed the search' point in opposite directions."""
        service = await self._service(settings, meeting)
        answer = await service.ask(
            "Kafka migration",
            scope=Scope.CORPUS,
            filters=Filters(speakers=["nobody-by-this-name"]),
        )

        assert answer.status is AnswerStatus.FILTERS_TOO_NARROW
        assert "Widening" in answer.answer

    async def test_indexing_is_incremental(self, settings, meeting):
        retrieval = StubRetrievalService(settings)
        count = await retrieval.index(meeting)
        assert count > 0
        assert await retrieval.index(meeting) == count
