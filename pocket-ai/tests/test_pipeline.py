"""Ingest, diarization, and the degradation behaviour of the pipeline."""

from __future__ import annotations

import pytest

from backend.app.models import SectionStatus, SpeakerSource, SpeakerTurn
from backend.app.services.diarization import (
    MIN_TURN_MS,
    DiarizationRefused,
    StubDiarizationService,
    merge_turns,
)
from backend.app.services.ingest import build_meeting, content_hash, parse_transcript
from backend.app.services.pipeline import apply_turns_to_transcript, process
from backend.app.services.registry import ServiceRegistry


class TestIngest:
    def test_meeting_id_is_the_audio_hash(self, meeting):
        assert meeting.id == content_hash(b"fake-audio-bytes")

    def test_same_audio_yields_the_same_id(self, meeting):
        """Re-uploading the same file must be a no-op, not a duplicate."""
        again = build_meeting(
            title="Different title entirely",
            occurred_at=meeting.occurred_at,
            audio_bytes=b"fake-audio-bytes",
            raw_transcript="[00:00:00] different words",
            duration_seconds=100,
        )
        assert again.id == meeting.id

    def test_parses_timestamps(self, meeting):
        assert meeting.transcript.segments[0].start_ms == 0
        assert meeting.transcript.segments[1].start_ms == 12_000
        assert meeting.transcript.segments[2].start_ms == 30_000

    def test_segment_ends_at_next_start(self, meeting):
        segs = meeting.transcript.segments
        assert segs[0].end_ms == segs[1].start_ms

    def test_untimed_lines_continue_from_previous(self):
        transcript = parse_transcript("[00:00:10] first\nsecond line with no stamp")
        assert len(transcript.segments) == 2
        assert transcript.segments[1].start_ms == transcript.segments[0].end_ms

    def test_blank_lines_are_dropped(self):
        assert len(parse_transcript("[00:00:00] one\n\n\n[00:00:05] two").segments) == 2

    def test_empty_transcript_yields_no_segments(self):
        assert parse_transcript("").segments == []


class TestTurnMerging:
    def test_merges_adjacent_same_speaker_turns(self):
        turns = [
            SpeakerTurn(start_ms=0, end_ms=1000, label="Speaker 1"),
            SpeakerTurn(start_ms=1200, end_ms=2000, label="Speaker 1"),
        ]
        merged = merge_turns(turns)
        assert len(merged) == 1
        assert merged[0].end_ms == 2000

    def test_does_not_merge_across_speakers(self):
        turns = [
            SpeakerTurn(start_ms=0, end_ms=1000, label="Speaker 1"),
            SpeakerTurn(start_ms=1100, end_ms=2000, label="Speaker 2"),
        ]
        assert len(merge_turns(turns)) == 2

    def test_does_not_merge_across_a_long_gap(self):
        turns = [
            SpeakerTurn(start_ms=0, end_ms=1000, label="Speaker 1"),
            SpeakerTurn(start_ms=5000, end_ms=6000, label="Speaker 1"),
        ]
        assert len(merge_turns(turns)) == 2

    def test_drops_backchannel_fragments(self):
        turns = [SpeakerTurn(start_ms=0, end_ms=MIN_TURN_MS - 50, label="Speaker 1")]
        assert merge_turns(turns) == []

    def test_empty_input(self):
        assert merge_turns([]) == []


class TestDiarizationQualityGate:
    async def test_refuses_unusable_audio(self, settings, bad_audio_meeting):
        """Better to decline than to burn compute producing confidently wrong turns."""
        service = StubDiarizationService(settings)
        with pytest.raises(DiarizationRefused):
            await service.diarize(bad_audio_meeting)

    async def test_accepts_good_audio(self, settings, meeting):
        turns = await StubDiarizationService(settings).diarize(meeting)
        assert turns


class TestAttribution:
    def test_manual_tags_are_never_overwritten(self, meeting):
        """A user correction outranks any model output, permanently."""
        segs = meeting.transcript.segments
        meeting.transcript = meeting.transcript.model_copy(
            update={
                "segments": [
                    segs[0].model_copy(
                        update={
                            "speaker_id": "manually-set",
                            "speaker_source": SpeakerSource.MANUAL,
                        }
                    ),
                    *segs[1:],
                ]
            }
        )
        meeting.turns = [
            SpeakerTurn(start_ms=0, end_ms=999_999, label="Speaker 9", speaker_id="model-guess")
        ]

        result = apply_turns_to_transcript(meeting)
        assert result.transcript.segments[0].speaker_id == "manually-set"
        assert result.transcript.segments[1].speaker_id == "model-guess"

    def test_no_turns_leaves_transcript_untouched(self, meeting):
        meeting.turns = []
        result = apply_turns_to_transcript(meeting)
        assert all(s.speaker_id is None for s in result.transcript.segments)


class TestPipelineDegradation:
    async def test_bad_audio_does_not_lose_the_meeting(self, settings, bad_audio_meeting):
        """Diarization failure costs attribution, not the whole meeting."""
        registry = ServiceRegistry(settings)
        meeting, insights = await process(bad_audio_meeting, registry)

        assert meeting.status.diarization.status is SectionStatus.FAILED
        assert meeting.status.diarization.reason
        # Everything else still ran.
        assert meeting.status.export.status is SectionStatus.OK
        assert meeting.status.enrichment.status is SectionStatus.OK
        assert meeting.status.indexing.status is SectionStatus.OK
        assert insights is not None

    async def test_happy_path_completes_every_stage(self, settings, meeting):
        registry = ServiceRegistry(settings)
        processed, insights = await process(meeting, registry)

        for stage in (
            processed.status.ingest,
            processed.status.export,
            processed.status.diarization,
            processed.status.identification,
            processed.status.enrichment,
            processed.status.indexing,
        ):
            assert stage.status is SectionStatus.OK

        assert insights is not None
        assert insights.mind_map is not None
