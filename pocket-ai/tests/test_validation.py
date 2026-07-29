"""Span validation — the mechanism that makes grounded generation enforceable.

If these tests pass but the validator is permissive, the whole citation guarantee is
decorative. The important cases are the negative ones.
"""

from __future__ import annotations

from backend.app.models import Cited, TranscriptSpan
from backend.app.services.validation import DefaultSpanValidator, normalize


class TestNormalize:
    def test_strips_punctuation_and_casing(self):
        assert normalize("Hello, World!") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize("a   b\n\nc") == "a b c"


class TestValidator:
    def setup_method(self):
        self.validator = DefaultSpanValidator()

    def test_exact_quote_validates(self, meeting):
        seg = meeting.transcript.segments[0]
        span = TranscriptSpan(
            meeting_id=meeting.id,
            segment_start=seg.index,
            segment_end=seg.index,
            quote=seg.text,
        )
        assert self.validator.validate(meeting, span)

    def test_punctuation_differences_still_validate(self, meeting):
        seg = meeting.transcript.segments[0]
        span = TranscriptSpan(
            meeting_id=meeting.id,
            segment_start=seg.index,
            segment_end=seg.index,
            quote=seg.text.upper().replace(",", ""),
        )
        assert self.validator.validate(meeting, span)

    def test_fabricated_quote_is_rejected(self, meeting):
        """The case the whole design exists for."""
        span = TranscriptSpan(
            meeting_id=meeting.id,
            segment_start=0,
            segment_end=0,
            quote="We agreed to ship the migration next week without further review.",
        )
        assert not self.validator.validate(meeting, span)

    def test_quote_from_wrong_meeting_is_rejected(self, meeting):
        span = TranscriptSpan(
            meeting_id="some-other-meeting",
            segment_start=0,
            segment_end=0,
            quote=meeting.transcript.segments[0].text,
        )
        assert not self.validator.validate(meeting, span)

    def test_quote_longer_than_source_is_rejected(self, meeting):
        """A hallucinated elaboration must not pass on partial overlap."""
        seg = meeting.transcript.segments[0]
        span = TranscriptSpan(
            meeting_id=meeting.id,
            segment_start=seg.index,
            segment_end=seg.index,
            quote=seg.text + " " + "and we also decided to cancel the project entirely" * 3,
        )
        assert not self.validator.validate(meeting, span)

    def test_empty_quote_is_rejected(self, meeting):
        span = TranscriptSpan(meeting_id=meeting.id, segment_start=0, segment_end=0, quote="   ")
        assert not self.validator.validate(meeting, span)

    def test_inverted_range_is_rejected(self, meeting):
        span = TranscriptSpan(
            meeting_id=meeting.id,
            segment_start=3,
            segment_end=1,
            quote=meeting.transcript.segments[1].text,
        )
        assert not self.validator.validate(meeting, span)

    def test_multi_segment_span_validates(self, meeting):
        segs = meeting.transcript.segments[:2]
        span = TranscriptSpan(
            meeting_id=meeting.id,
            segment_start=segs[0].index,
            segment_end=segs[1].index,
            quote=segs[1].text,
        )
        assert self.validator.validate(meeting, span)

    def test_validate_all_requires_at_least_one_span(self, meeting):
        assert not self.validator.validate_all(meeting, [])


class TestFiltering:
    def setup_method(self):
        self.validator = DefaultSpanValidator()

    def test_uncited_claims_are_dropped_not_flagged(self, meeting):
        good = Cited[str](
            value="real",
            spans=[
                TranscriptSpan(
                    meeting_id=meeting.id,
                    segment_start=0,
                    segment_end=0,
                    quote=meeting.transcript.segments[0].text,
                )
            ],
        )
        bad = Cited[str](
            value="fabricated",
            spans=[
                TranscriptSpan(
                    meeting_id=meeting.id,
                    segment_start=0,
                    segment_end=0,
                    quote="something nobody said in this meeting at all",
                )
            ],
        )
        kept = self.validator.filter_cited(meeting, [good, bad])
        assert [c.value for c in kept] == ["real"]

    def test_keep_if_valid_returns_none_for_bad_citation(self, meeting):
        bad = Cited[str](
            value="fabricated",
            spans=[
                TranscriptSpan(
                    meeting_id=meeting.id,
                    segment_start=0,
                    segment_end=0,
                    quote="entirely invented content that appears nowhere",
                )
            ],
        )
        assert self.validator.keep_if_valid(meeting, bad) is None

    def test_keep_if_valid_passes_none_through(self, meeting):
        assert self.validator.keep_if_valid(meeting, None) is None
