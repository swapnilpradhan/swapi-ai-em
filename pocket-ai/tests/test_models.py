"""Domain model invariants.

These test the constraints the model exists to enforce — consent gating, commitment
classification, folder naming — rather than Pydantic itself.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.models import (
    ActionItem,
    Cited,
    CommitmentType,
    ConsentRecord,
    ConsentScope,
    Speaker,
    TranscriptSpan,
    Voiceprint,
    VoiceprintLibrary,
)


def _consent(scope: ConsentScope) -> ConsentRecord:
    return ConsentRecord(granted_at=datetime.now(UTC), method="written", scope=scope)


def _voiceprint() -> Voiceprint:
    return Voiceprint(
        embeddings=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]], enrolled_at=datetime.now(UTC)
    )


class TestConsent:
    def test_voiceprint_requires_voiceprint_scope(self):
        """Recording consent alone must not permit storing a biometric identifier."""
        with pytest.raises(ValidationError, match="consent scope"):
            Speaker(
                display_name="Priya",
                consent=_consent(ConsentScope.RECORDING_ONLY),
                voiceprint=_voiceprint(),
            )

    def test_voiceprint_allowed_with_correct_scope(self):
        speaker = Speaker(
            display_name="Priya",
            consent=_consent(ConsentScope.RECORDING_AND_VOICEPRINT),
            voiceprint=_voiceprint(),
        )
        assert speaker.voiceprint is not None
        assert speaker.voiceprint.sample_count == 3

    def test_speaker_without_voiceprint_needs_only_recording_consent(self):
        speaker = Speaker(display_name="Marcus", consent=_consent(ConsentScope.RECORDING_ONLY))
        assert speaker.voiceprint is None

    def test_revocation_drops_the_voiceprint(self):
        speaker = Speaker(
            display_name="Priya",
            consent=_consent(ConsentScope.RECORDING_AND_VOICEPRINT),
            voiceprint=_voiceprint(),
        )
        revoked = speaker.revoke_consent(datetime.now(UTC))
        assert revoked.voiceprint is None
        assert not revoked.consent.is_active

    def test_revoked_consent_no_longer_permits_voiceprint(self):
        consent = _consent(ConsentScope.RECORDING_AND_VOICEPRINT).model_copy(
            update={"revoked_at": datetime.now(UTC)}
        )
        assert not consent.permits_voiceprint


class TestVoiceprintLibrary:
    def test_enrolling_bumps_version(self):
        """Version participates in the identification cache key (ADR-0003)."""
        library = VoiceprintLibrary()
        assert library.version == 1

        updated = library.with_speaker(
            Speaker(display_name="Priya", consent=_consent(ConsentScope.RECORDING_ONLY))
        )
        assert updated.version == 2

    def test_enrolled_excludes_speakers_without_voiceprints(self):
        library = VoiceprintLibrary().with_speaker(
            Speaker(display_name="Marcus", consent=_consent(ConsentScope.RECORDING_ONLY))
        )
        assert library.speakers
        assert library.enrolled() == []


class TestCited:
    def test_cited_requires_at_least_one_span(self):
        """An uncited claim must not be constructible."""
        with pytest.raises(ValidationError):
            Cited[str](value="something asserted", spans=[])

    def test_cited_with_span_is_valid(self):
        span = TranscriptSpan(meeting_id="m1", segment_start=0, segment_end=1, quote="hello")
        assert Cited[str](value="claim", spans=[span]).spans


class TestSpanOverlap:
    def test_overlapping_spans_in_same_meeting(self):
        a = TranscriptSpan(meeting_id="m1", segment_start=0, segment_end=5, quote="a")
        b = TranscriptSpan(meeting_id="m1", segment_start=3, segment_end=8, quote="b")
        assert a.overlaps(b)

    def test_spans_in_different_meetings_never_overlap(self):
        a = TranscriptSpan(meeting_id="m1", segment_start=0, segment_end=5, quote="a")
        b = TranscriptSpan(meeting_id="m2", segment_start=0, segment_end=5, quote="b")
        assert not a.overlaps(b)

    def test_disjoint_spans(self):
        a = TranscriptSpan(meeting_id="m1", segment_start=0, segment_end=2, quote="a")
        b = TranscriptSpan(meeting_id="m1", segment_start=5, segment_end=8, quote="b")
        assert not a.overlaps(b)


class TestActionItem:
    def test_hypotheticals_are_never_surfaced(self):
        """'Someone should probably...' is not a task, at any confidence."""
        item = ActionItem(
            description="Review the retention policy",
            commitment_type=CommitmentType.HYPOTHETICAL,
            confidence=0.99,
        )
        assert not item.is_surfaceable

    def test_mid_confidence_items_queue_for_confirmation(self):
        item = ActionItem(
            description="Take a look at the dashboard",
            commitment_type=CommitmentType.SOFT,
            confidence=0.6,
        )
        assert item.needs_confirmation
        assert item.is_surfaceable

    def test_user_confirmation_overrides_low_confidence(self):
        item = ActionItem(
            description="Send the plan",
            commitment_type=CommitmentType.FIRM,
            confidence=0.1,
            confirmed_by_user=True,
        )
        assert item.is_surfaceable
        assert not item.needs_confirmation

    def test_high_confidence_needs_no_confirmation(self):
        item = ActionItem(
            description="Run the capacity analysis",
            commitment_type=CommitmentType.FIRM,
            confidence=0.9,
        )
        assert item.is_surfaceable
        assert not item.needs_confirmation


class TestFolderName:
    def test_folder_name_format(self, meeting):
        assert meeting.folder_name == "2026-07-29 — Platform Architecture Review"

    def test_path_separators_are_stripped(self, meeting):
        renamed = meeting.model_copy(update={"title": "Q3/Q4 Planning"})
        assert "/" not in renamed.folder_name
        assert renamed.folder_name.endswith("Q3Q4 Planning")

    def test_long_titles_are_truncated(self, meeting):
        renamed = meeting.model_copy(update={"title": "A" * 300})
        title_part = renamed.folder_name.split(" — ", 1)[1]
        assert len(title_part) == 120

    def test_empty_title_falls_back(self, meeting):
        renamed = meeting.model_copy(update={"title": "   "})
        assert renamed.folder_name.endswith("Untitled")
