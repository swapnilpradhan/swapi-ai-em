"""Pocket payload parsing.

The field names here are unverified against the real spec, so the parser is written
to be tolerant. These tests pin that tolerance: a naming difference should degrade to
a missing optional field, never to a failed ingest.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from backend.app.services.ingest import (
    build_meeting_from_pocket,
    canonical_transcript_hash,
    transcript_from_pocket,
)
from backend.app.services.pocket import (
    PocketRecording,
    PocketSegment,
    StubPocketClient,
    parse_recording,
    parse_segments,
)


class TestSegmentParsing:
    def test_parses_documented_shape(self):
        """`{text, start, end, speaker?}` with seconds — the documented contract."""
        segments = parse_segments(
            [
                {"text": "Hello there", "start": 0.0, "end": 2.5, "speaker": "Speaker 1"},
                {"text": "Hi back", "start": 2.5, "end": 4.0},
            ]
        )

        assert len(segments) == 2
        assert segments[0].start_ms == 0
        assert segments[0].end_ms == 2500
        assert segments[0].speaker == "Speaker 1"
        assert segments[1].speaker is None

    def test_accepts_alternative_field_spellings(self):
        segments = parse_segments(
            [{"content": "Hello", "startTime": 1, "endTime": 2, "speakerLabel": "A"}]
        )
        assert segments[0].text == "Hello"
        assert segments[0].start_ms == 1000
        assert segments[0].speaker == "A"

    def test_unwraps_a_container_object(self):
        assert len(parse_segments({"segments": [{"text": "x", "start": 0, "end": 1}]})) == 1

    def test_drops_empty_and_malformed_entries(self):
        segments = parse_segments(
            [{"text": "   ", "start": 0, "end": 1}, "not-a-dict", {"start": 0, "end": 1}]
        )
        assert segments == []

    def test_missing_timings_do_not_raise(self):
        segments = parse_segments([{"text": "no timings"}])
        assert segments[0].start_ms == 0
        assert segments[0].end_ms == 0

    def test_end_never_precedes_start(self):
        segments = parse_segments([{"text": "x", "start": 5, "end": 1}])
        assert segments[0].end_ms >= segments[0].start_ms

    def test_non_list_input_yields_nothing(self):
        assert parse_segments(None) == []
        assert parse_segments("garbage") == []


class TestRecordingParsing:
    def test_parses_documented_shape(self):
        recording = parse_recording(
            {
                "recordingId": "rec_123",
                "recordingTitle": "Platform Review",
                "recordingDate": "2026-07-29T10:00:00Z",
                "recordingTags": ["work"],
                "audioUrl": "https://example.test/a.m4a",
                "summary": "a summary",
                "segments": [{"text": "hi", "start": 0, "end": 3}],
            }
        )

        assert recording.recording_id == "rec_123"
        assert recording.title == "Platform Review"
        assert recording.occurred_at == datetime(2026, 7, 29, 10, 0, tzinfo=UTC)
        assert recording.tags == ["work"]
        assert recording.audio_url

    def test_missing_id_is_an_error(self):
        """The id is the one field we genuinely cannot work without."""
        with pytest.raises(ValueError):
            parse_recording({"title": "no id"})

    def test_duration_falls_back_to_transcript_span(self):
        recording = parse_recording(
            {"id": "r1", "segments": [{"text": "x", "start": 0, "end": 42}]}
        )
        assert recording.duration_seconds == pytest.approx(42.0)

    def test_missing_date_defaults_to_now_not_epoch(self):
        recording = parse_recording({"id": "r1", "segments": []})
        assert recording.occurred_at.year >= 2026

    def test_naive_timestamps_get_utc(self):
        recording = parse_recording({"id": "r1", "recordingDate": "2026-07-29T10:00:00"})
        assert recording.occurred_at.tzinfo is not None

    def test_unparseable_date_does_not_raise(self):
        assert parse_recording({"id": "r1", "recordingDate": "not a date"}).occurred_at

    def test_has_speaker_labels_detection(self):
        with_labels = parse_recording(
            {"id": "r1", "segments": [{"text": "x", "start": 0, "end": 1, "speaker": "S1"}]}
        )
        without = parse_recording({"id": "r2", "segments": [{"text": "x", "start": 0, "end": 1}]})

        assert with_labels.has_speaker_labels
        assert not without.has_speaker_labels


class TestStubClient:
    async def test_returns_speaker_labels(self, settings):
        """The stub models the behaviour that drives the pipeline short-circuit."""
        recording = await StubPocketClient(settings).get_recording("rec_1")
        assert recording.has_speaker_labels

    async def test_list_terminates(self, settings):
        client = StubPocketClient(settings)
        page, cursor = await client.list_recordings()
        assert page
        assert cursor is None


class TestMapping:
    def _recording(self, *, speaker: str | None = "Speaker 1") -> PocketRecording:
        return PocketRecording(
            recording_id="rec_1",
            title="Review",
            occurred_at=datetime(2026, 7, 29, tzinfo=UTC),
            duration_seconds=60.0,
            segments=[
                PocketSegment(text="one", start_ms=0, end_ms=1000, speaker=speaker),
                PocketSegment(text="two", start_ms=1000, end_ms=2000, speaker=speaker),
            ],
        )

    def test_speaker_becomes_a_label_not_an_id(self):
        """Upstream says which *voice*, not which *person*."""
        transcript = transcript_from_pocket(self._recording())

        assert transcript.segments[0].speaker_label == "Speaker 1"
        assert transcript.segments[0].speaker_id is None
        assert transcript.has_speaker_labels
        assert not transcript.is_attributed

    def test_no_speaker_means_no_labels(self):
        transcript = transcript_from_pocket(self._recording(speaker=None))
        assert not transcript.has_speaker_labels

    def test_external_ref_is_recorded(self):
        meeting = build_meeting_from_pocket(self._recording())
        assert meeting.external_ref is not None
        assert meeting.external_ref.key == "pocket:rec_1"

    def test_identity_is_stable_without_audio(self):
        """Re-fetching unchanged content must converge on the same meeting id."""
        first = build_meeting_from_pocket(self._recording())
        second = build_meeting_from_pocket(self._recording())
        assert first.id == second.id

    def test_identity_prefers_audio_hash(self):
        from backend.app.services.ingest import content_hash

        meeting = build_meeting_from_pocket(self._recording(), audio_bytes=b"audio")
        assert meeting.id == content_hash(b"audio")

    def test_transcript_hash_changes_with_content(self):
        other = self._recording()
        changed = PocketRecording(
            recording_id=other.recording_id,
            title=other.title,
            occurred_at=other.occurred_at,
            duration_seconds=other.duration_seconds,
            segments=[PocketSegment(text="different", start_ms=0, end_ms=1000)],
        )
        assert canonical_transcript_hash(other) != canonical_transcript_hash(changed)

    def test_transcript_hash_ignores_unrelated_metadata(self):
        """A title change upstream must not mint a new meeting."""
        base = self._recording()
        retitled = PocketRecording(
            recording_id=base.recording_id,
            title="Completely different title",
            occurred_at=base.occurred_at,
            duration_seconds=base.duration_seconds,
            segments=base.segments,
        )
        assert canonical_transcript_hash(base) == canonical_transcript_hash(retitled)

    def test_distinct_recordings_stay_distinct_without_audio(self):
        """Identical text in two real recordings must not collapse into one meeting.

        Without audio the transcript is all we have, and a short standup can easily
        repeat verbatim. Collapsing would drop one from the external-ref index.
        """
        first = self._recording()
        second = PocketRecording(
            recording_id="rec_2",
            title=first.title,
            occurred_at=first.occurred_at,
            duration_seconds=first.duration_seconds,
            segments=first.segments,
        )
        assert canonical_transcript_hash(first) != canonical_transcript_hash(second)


class TestCheckAccess:
    """`check_access` is the answer to "did my auth work?" — the negative paths matter."""

    async def test_reports_shape_not_content(self, settings):
        from backend.app.services.pocket import check_access

        result = await check_access(StubPocketClient(settings))

        assert result["ok"] is True
        assert result["authenticated"] is True
        assert result["speaker_labels_present"] is True
        assert result["segment_count"] > 0
        # A diagnostic must never leak transcript text.
        assert "text" not in json.dumps(result).lower() or "context" in json.dumps(result)
        assert not any("migration timeline" in str(v) for v in result.values())

    async def test_bad_key_is_reported_not_raised(self, settings):
        from backend.app.services.pocket import PocketAuthError, check_access

        class BadKey:
            async def list_recordings(self, **kwargs):
                raise PocketAuthError("Pocket API rejected the key (401)")

        result = await check_access(BadKey())

        assert result["ok"] is False
        assert result["authenticated"] is False
        assert "Developer" in result["hint"]

    async def test_empty_account_is_not_a_failure(self, settings):
        from backend.app.services.pocket import check_access

        class Empty:
            async def list_recordings(self, **kwargs):
                return [], None

        result = await check_access(Empty())

        assert result["ok"] is True
        assert result["recordings_visible"] == 0

    async def test_missing_transcripts_hints_at_the_plan(self, settings):
        """The Pro gate looks exactly like a parser bug; say so explicitly."""
        from backend.app.services.pocket import check_access

        bare = PocketRecording(
            recording_id="r1",
            title="Untitled",
            occurred_at=datetime(2026, 7, 29, tzinfo=UTC),
            duration_seconds=60.0,
            segments=[],
        )

        class NoTranscript:
            async def list_recordings(self, **kwargs):
                return [bare], None

            async def get_recording(self, recording_id):
                return bare

        result = await check_access(NoTranscript())

        assert result["ok"] is True
        assert result["transcript_accessible"] is False
        assert "Pocket Pro" in result["hint"]

    async def test_unlabelled_transcript_hints_at_diarization(self, settings):
        from backend.app.services.pocket import check_access

        unlabelled = PocketRecording(
            recording_id="r1",
            title="Untitled",
            occurred_at=datetime(2026, 7, 29, tzinfo=UTC),
            duration_seconds=60.0,
            segments=[PocketSegment(text="hello", start_ms=0, end_ms=1000)],
        )

        class Unlabelled:
            async def list_recordings(self, **kwargs):
                return [unlabelled], None

            async def get_recording(self, recording_id):
                return unlabelled

        result = await check_access(Unlabelled())

        assert result["speaker_labels_present"] is False
        assert "diarization" in result["hint"]

    async def test_network_failure_does_not_raise(self, settings):
        from backend.app.services.pocket import check_access

        class Broken:
            async def list_recordings(self, **kwargs):
                raise RuntimeError("connection refused")

        result = await check_access(Broken())

        assert result["ok"] is False
        assert "connection refused" in result["reason"]
