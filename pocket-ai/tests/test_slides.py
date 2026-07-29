"""Deck structure validation and the review gate.

The argument is the deliverable; these test that a broken argument is caught before
anything gets rendered.
"""

from __future__ import annotations

from backend.app.agents.slide_builder import (
    MAX_ARGUMENTS,
    Argument,
    DeckStructure,
    Slide,
    SlideBody,
    StubSlideBuilder,
    render_outline,
    validate_mece,
)
from backend.app.models import Cited, TranscriptSpan


def _span(start: int, end: int, quote: str = "quote") -> TranscriptSpan:
    return TranscriptSpan(meeting_id="m1", segment_start=start, segment_end=end, quote=quote)


def _structure(arguments: list[Argument]) -> DeckStructure:
    return DeckStructure(
        governing_thought=Cited[str](value="The thing this deck proves", spans=[_span(0, 0)]),
        arguments=arguments,
    )


class TestMECEValidation:
    def test_clean_decomposition_passes(self):
        structure = _structure(
            [
                Argument(assertion="First", spans=[_span(0, 2)]),
                Argument(assertion="Second", spans=[_span(5, 7)]),
                Argument(assertion="Third", spans=[_span(10, 12)]),
            ]
        )
        assert validate_mece(structure) == []

    def test_overlapping_evidence_is_flagged(self):
        """Two arguments citing the same evidence are not distinct claims."""
        structure = _structure(
            [
                Argument(assertion="First", spans=[_span(0, 5)]),
                Argument(assertion="Second", spans=[_span(3, 8)]),
            ]
        )
        violations = validate_mece(structure)
        assert any(v.kind == "overlap" for v in violations)

    def test_argument_without_evidence_is_flagged(self):
        structure = _structure(
            [
                Argument(assertion="Supported", spans=[_span(0, 2)]),
                Argument(assertion="Unsupported", spans=[]),
            ]
        )
        violations = validate_mece(structure)
        assert any(v.kind == "coverage" for v in violations)

    def test_too_few_arguments_is_flagged(self):
        structure = _structure([Argument(assertion="Only one", spans=[_span(0, 2)])])
        assert any(v.kind == "count" for v in validate_mece(structure))

    def test_too_many_arguments_is_flagged(self):
        structure = _structure(
            [
                Argument(assertion=f"Arg {i}", spans=[_span(i * 10, i * 10 + 2)])
                for i in range(MAX_ARGUMENTS + 2)
            ]
        )
        assert any(v.kind == "count" for v in validate_mece(structure))


class TestOutline:
    def test_title_thread_is_the_argument(self):
        """Reading the titles alone must give the whole argument."""
        structure = _structure(
            [
                Argument(
                    assertion="First",
                    spans=[_span(0, 2)],
                    slides=[Slide(action_title="Margin compression is in enterprise")],
                ),
                Argument(
                    assertion="Second",
                    spans=[_span(5, 7)],
                    slides=[Slide(action_title="Enterprise churn drives the gap")],
                ),
            ]
        )
        assert structure.title_thread() == [
            "Margin compression is in enterprise",
            "Enterprise churn drives the gap",
        ]

    def test_outline_includes_governing_thought_and_thread(self):
        structure = _structure(
            [
                Argument(
                    assertion="First",
                    spans=[_span(0, 2)],
                    slides=[
                        Slide(
                            action_title="An assertion",
                            body=SlideBody(content=["evidence"]),
                            so_what="the implication",
                        )
                    ],
                ),
                Argument(assertion="Second", spans=[_span(5, 7)]),
            ]
        )
        outline = render_outline(structure)

        assert "# The thing this deck proves" in outline
        assert "## Title thread" in outline
        assert "An assertion" in outline
        assert "*So what:* the implication" in outline


class TestStubBuilder:
    async def test_builds_a_valid_structure(self, settings, meeting):
        from backend.app.services.llm import StubLLMService

        builder = StubSlideBuilder(settings, StubLLMService(settings))
        structure = await builder.build_structure(meeting)

        assert structure.governing_thought.spans
        assert structure.arguments
        assert structure.title_thread()

    async def test_empty_transcript_fails_rather_than_padding(self, settings, meeting):
        """A meeting with nothing to argue must not produce a deck."""
        import pytest

        from backend.app.services.llm import StubLLMService

        empty = meeting.model_copy(
            update={"transcript": meeting.transcript.model_copy(update={"segments": []})}
        )
        builder = StubSlideBuilder(settings, StubLLMService(settings))

        with pytest.raises(ValueError):
            await builder.build_structure(empty)

    async def test_render_emits_the_outline(self, settings, meeting):
        from backend.app.services.llm import StubLLMService

        builder = StubSlideBuilder(settings, StubLLMService(settings))
        structure = await builder.build_structure(meeting)
        content = await builder.render(structure)

        assert b"Title thread" in content
