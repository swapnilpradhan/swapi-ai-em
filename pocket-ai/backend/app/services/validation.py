"""Span validation — the mechanical enforcement of grounded generation.

A generated claim carries a quote and a segment range. This checks that the quote
actually appears in those segments. Claims that fail are dropped, not flagged: a
shorter summary that is entirely true beats a complete one that is mostly true.

See docs/adr/0004-grounded-generation.md.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import TypeVar

from ..models import Cited, Meeting, TranscriptSpan

T = TypeVar("T")

# Transcription reformatting (punctuation, casing, whitespace) shouldn't fail a
# citation that is substantively correct, so match on normalized text with a high
# similarity floor rather than requiring an exact substring.
_SIMILARITY_FLOOR = 0.85
_NON_WORD = re.compile(r"[^\w\s]")


def normalize(text: str) -> str:
    return " ".join(_NON_WORD.sub(" ", text).lower().split())


class DefaultSpanValidator:
    """Validates spans against a meeting's transcript."""

    def __init__(self, similarity_floor: float = _SIMILARITY_FLOOR) -> None:
        self.similarity_floor = similarity_floor

    def validate(self, meeting: Meeting, span: TranscriptSpan) -> bool:
        if span.meeting_id != meeting.id:
            return False
        if span.segment_end < span.segment_start:
            return False

        source = normalize(meeting.transcript.text_for_span(span))
        quote = normalize(span.quote)
        if not quote or not source:
            return False
        if quote in source:
            return True

        # A quote longer than its source can never be contained in it; comparing them
        # with a ratio would let a hallucinated elaboration slip through on partial
        # overlap with a short segment.
        if len(quote) > len(source):
            return False
        return SequenceMatcher(None, quote, source).ratio() >= self.similarity_floor

    def validate_all(self, meeting: Meeting, spans: list[TranscriptSpan]) -> bool:
        return bool(spans) and all(self.validate(meeting, s) for s in spans)

    def filter_cited(self, meeting: Meeting, items: list[Cited[T]]) -> list[Cited[T]]:
        """Drop claims whose citations do not hold up."""
        return [c for c in items if self.validate_all(meeting, c.spans)]

    def keep_if_valid(self, meeting: Meeting, item: Cited[T] | None) -> Cited[T] | None:
        if item is None:
            return None
        return item if self.validate_all(meeting, item.spans) else None
