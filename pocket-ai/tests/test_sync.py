"""Ingest orchestration: dedupe, degradation, and the diarization short-circuit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.app.api.store import MemoryStore
from backend.app.models import SectionStatus, SpeakerSource
from backend.app.services.pocket import (
    PocketAuthError,
    PocketNotFound,
    PocketRecording,
    PocketSegment,
    StubPocketClient,
)
from backend.app.services.registry import ServiceRegistry
from backend.app.services.sync import IngestOutcome, backfill, ingest_recording


def _recording(
    recording_id: str = "rec_1",
    *,
    speaker: str | None = "Speaker 1",
    updated_at: datetime | None = None,
    segments: list[PocketSegment] | None = None,
) -> PocketRecording:
    return PocketRecording(
        recording_id=recording_id,
        title="Platform Review",
        occurred_at=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
        duration_seconds=120.0,
        segments=segments
        if segments is not None
        else [
            PocketSegment(
                text="Let's discuss the timeline.", start_ms=0, end_ms=5000, speaker=speaker
            ),
            PocketSegment(
                text="I'll run the analysis by Friday.",
                start_ms=5000,
                end_ms=11000,
                speaker="Speaker 2" if speaker else None,
            ),
        ],
        updated_at=updated_at,
    )


class FakePocketClient:
    """Scriptable client for the paths the stub cannot express."""

    def __init__(self, recordings=None, *, error: Exception | None = None):
        self.recordings = {r.recording_id: r for r in (recordings or [])}
        self.error = error
        self.fetch_count = 0

    async def get_recording(self, recording_id: str) -> PocketRecording:
        self.fetch_count += 1
        if self.error:
            raise self.error
        if recording_id not in self.recordings:
            raise PocketNotFound(recording_id)
        return self.recordings[recording_id]

    async def list_recordings(self, *, limit: int = 50, cursor: str | None = None):
        if cursor:
            return [], None
        return list(self.recordings.values()), None

    async def download_audio(self, recording):
        return None


def _registry(settings, client) -> ServiceRegistry:
    registry = ServiceRegistry(settings)
    registry.pocket = client
    return registry


class TestIngestRecording:
    async def test_processes_a_new_recording(self, settings):
        store = MemoryStore()
        registry = _registry(settings, FakePocketClient([_recording()]))

        result = await ingest_recording("rec_1", registry, store)

        assert result.outcome is IngestOutcome.PROCESSED
        assert store.get_by_external("pocket", "rec_1") is not None

    async def test_redelivery_is_a_cheap_no_op(self, settings):
        """Webhook delivery is at-least-once; the second call must not duplicate."""
        store = MemoryStore()
        client = FakePocketClient([_recording(updated_at=datetime(2026, 7, 29, tzinfo=UTC))])
        registry = _registry(settings, client)

        first = await ingest_recording("rec_1", registry, store)
        second = await ingest_recording("rec_1", registry, store)

        assert first.outcome is IngestOutcome.PROCESSED
        assert second.outcome is IngestOutcome.ALREADY_CURRENT
        assert second.meeting_id == first.meeting_id
        assert len(store.meetings) == 1

    async def test_upstream_edit_is_reprocessed(self, settings):
        """A genuine revision must get through the dedupe check."""
        store = MemoryStore()
        early = datetime(2026, 7, 29, 10, 0, tzinfo=UTC)
        client = FakePocketClient([_recording(updated_at=early)])
        registry = _registry(settings, client)

        await ingest_recording("rec_1", registry, store)

        client.recordings["rec_1"] = _recording(
            updated_at=early + timedelta(hours=1),
            segments=[PocketSegment(text="Revised content entirely.", start_ms=0, end_ms=4000)],
        )
        result = await ingest_recording("rec_1", registry, store)

        assert result.outcome is IngestOutcome.PROCESSED

    async def test_force_reprocesses_unchanged_content(self, settings):
        store = MemoryStore()
        registry = _registry(settings, FakePocketClient([_recording()]))

        await ingest_recording("rec_1", registry, store)
        result = await ingest_recording("rec_1", registry, store, force=True)

        assert result.outcome is IngestOutcome.PROCESSED

    async def test_missing_recording_is_reported_not_raised(self, settings):
        registry = _registry(settings, FakePocketClient([]))
        result = await ingest_recording("nope", registry, MemoryStore())
        assert result.outcome is IngestOutcome.NOT_FOUND

    async def test_auth_failure_is_surfaced(self, settings):
        """A broken key must not fail silently — the user has to learn about it."""
        registry = _registry(settings, FakePocketClient(error=PocketAuthError("bad key")))
        result = await ingest_recording("rec_1", registry, MemoryStore())

        assert result.outcome is IngestOutcome.FAILED
        assert "bad key" in (result.reason or "")

    async def test_transcript_not_ready_yet(self, settings):
        """A completion hook can beat transcription; a later event brings us back."""
        registry = _registry(settings, FakePocketClient([_recording(segments=[])]))
        result = await ingest_recording("rec_1", registry, MemoryStore())
        assert result.outcome is IngestOutcome.NO_TRANSCRIPT

    async def test_manual_speaker_tags_survive_a_resync(self, settings):
        """Losing the user's corrections on re-sync would be a trust-killer."""
        store = MemoryStore()
        early = datetime(2026, 7, 29, 10, 0, tzinfo=UTC)
        client = FakePocketClient([_recording(updated_at=early)])
        registry = _registry(settings, client)

        await ingest_recording("rec_1", registry, store)
        meeting = store.get_by_external("pocket", "rec_1")

        meeting.transcript = meeting.transcript.model_copy(
            update={
                "segments": [
                    meeting.transcript.segments[0].model_copy(
                        update={
                            "speaker_id": "priya-id",
                            "speaker_source": SpeakerSource.MANUAL,
                        }
                    ),
                    *meeting.transcript.segments[1:],
                ]
            }
        )
        store.put_meeting(meeting)

        client.recordings["rec_1"] = _recording(updated_at=early + timedelta(hours=1))
        await ingest_recording("rec_1", registry, store)

        resynced = store.get_by_external("pocket", "rec_1")
        assert resynced.transcript.segments[0].speaker_id == "priya-id"
        assert resynced.transcript.segments[0].speaker_source is SpeakerSource.MANUAL


class TestDiarizationShortCircuit:
    async def test_source_labels_skip_diarization(self, settings):
        """The scope reduction: upstream already separated the voices."""
        store = MemoryStore()
        registry = _registry(settings, FakePocketClient([_recording(speaker="Speaker 1")]))

        await ingest_recording("rec_1", registry, store)
        meeting = store.get_by_external("pocket", "rec_1")

        assert meeting.status.diarization.status is SectionStatus.SKIPPED
        assert "source provided" in meeting.status.diarization.reason
        assert meeting.status.identification.status is SectionStatus.OK
        assert meeting.turns

    async def test_turns_are_derived_from_labels(self, settings):
        store = MemoryStore()
        registry = _registry(settings, FakePocketClient([_recording(speaker="Speaker 1")]))

        await ingest_recording("rec_1", registry, store)
        meeting = store.get_by_external("pocket", "rec_1")

        assert [t.label for t in meeting.turns] == ["Speaker 1", "Speaker 2"]

    async def test_unlabelled_source_still_diarizes(self, settings):
        """Without labels we fall back to doing the work ourselves."""
        store = MemoryStore()
        registry = _registry(settings, FakePocketClient([_recording(speaker=None)]))

        await ingest_recording("rec_1", registry, store)
        meeting = store.get_by_external("pocket", "rec_1")

        assert meeting.status.diarization.status is SectionStatus.OK


class TestTurnDerivation:
    def test_consecutive_same_speaker_segments_merge(self, meeting):
        from backend.app.services.pipeline import turns_from_transcript_labels

        segments = [
            s.model_copy(update={"speaker_label": "A" if s.index < 2 else "B"})
            for s in meeting.transcript.segments
        ]
        meeting.transcript = meeting.transcript.model_copy(update={"segments": segments})

        turns = turns_from_transcript_labels(meeting)

        assert [t.label for t in turns] == ["A", "B"]
        assert turns[0].end_ms == segments[1].end_ms

    def test_unlabelled_segments_produce_no_turns(self, meeting):
        from backend.app.services.pipeline import turns_from_transcript_labels

        assert turns_from_transcript_labels(meeting) == []


class TestBackfill:
    async def test_walks_history_through_the_same_path(self, settings):
        store = MemoryStore()
        client = FakePocketClient([_recording("rec_1"), _recording("rec_2")])
        registry = _registry(settings, client)

        results = await backfill(registry, store, max_recordings=10)

        assert len(results) == 2
        assert all(r.outcome is IngestOutcome.PROCESSED for r in results)
        assert len(store.meetings) == 2

    async def test_respects_the_cap(self, settings):
        """A first run against a large archive must not become an unbounded job."""
        store = MemoryStore()
        client = FakePocketClient([_recording(f"rec_{i}") for i in range(10)])
        registry = _registry(settings, client)

        results = await backfill(registry, store, max_recordings=3)
        assert len(results) == 3

    async def test_terminates_on_empty_history(self, settings):
        registry = _registry(settings, FakePocketClient([]))
        assert await backfill(registry, MemoryStore()) == []

    async def test_stub_client_backfills(self, settings):
        store = MemoryStore()
        registry = _registry(settings, StubPocketClient(settings))

        results = await backfill(registry, store, max_recordings=10)
        assert results
