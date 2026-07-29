"""Service interfaces.

Every external dependency sits behind a Protocol with at least two implementations: a
real one and a stub. The stub is production-quality code, not a test fixture — the
full pipeline runs on stubs with zero credentials.

Nothing outside ``registry.py`` should import a concrete implementation.

See docs/adr/0005-stub-first-service-protocols.md.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import (
    Artifact,
    Chunk,
    CitedAnswer,
    CoachingAssessment,
    CoachingDigest,
    CoachingTrack,
    DateRange,
    Drill,
    ExportManifest,
    ExportResult,
    Filters,
    Meeting,
    MeetingInsights,
    ModelTier,
    Scope,
    SpeakerTurn,
    TranscriptSpan,
    VoiceprintLibrary,
)


@runtime_checkable
class StorageService(Protocol):
    """Artifact export. See docs/capabilities/01-drive-export.md."""

    async def ensure_meeting_folder(self, meeting: Meeting) -> str: ...

    async def export(self, meeting: Meeting, artifact: Artifact) -> ExportResult: ...

    async def export_all(self, meeting: Meeting, artifacts: list[Artifact]) -> ExportManifest: ...

    async def read_manifest(self, meeting_id: str) -> ExportManifest | None: ...


@runtime_checkable
class DiarizationService(Protocol):
    """Audio → anonymous speaker turns. Cache key: ``audio_hash``.

    Kept separate from identification so the expensive audio pass runs exactly once
    per file, ever. See docs/adr/0003-diarization-separate-from-identification.md.
    """

    async def diarize(self, meeting: Meeting) -> list[SpeakerTurn]: ...


@runtime_checkable
class IdentificationService(Protocol):
    """Anonymous turns + voiceprints → named turns.

    Cache key: ``(audio_hash, library_version)``. Turns marked ``SpeakerSource.MANUAL``
    are never touched.
    """

    async def identify(
        self, turns: list[SpeakerTurn], library: VoiceprintLibrary
    ) -> list[SpeakerTurn]: ...


@runtime_checkable
class LLMService(Protocol):
    """Model access, routed by tier rather than by hard-coded model id."""

    async def complete(self, prompt: str, *, tier: ModelTier = ModelTier.FAST) -> str: ...


@runtime_checkable
class InsightsService(Protocol):
    """Summaries, decisions, action items, mind maps.

    Everything produced here carries spans that pass validation, or is dropped.
    See docs/adr/0004-grounded-generation.md.
    """

    async def enrich(self, meeting: Meeting) -> MeetingInsights: ...


@runtime_checkable
class RetrievalService(Protocol):
    """Corpus index. Incremental — never re-embeds everything except on rebuild."""

    async def index(self, meeting: Meeting) -> int: ...

    async def search(
        self, query: str, *, scope: Scope, filters: Filters, k: int = 12
    ) -> list[Chunk]: ...


@runtime_checkable
class ChatService(Protocol):
    """Grounded Q&A over the corpus. Refuses rather than answering from outside it."""

    async def ask(self, question: str, *, scope: Scope, filters: Filters) -> CitedAnswer: ...


@runtime_checkable
class CoachService(Protocol):
    """Executive development. No output without evidence from the user's own material."""

    async def assess(self, *, track: CoachingTrack, window: DateRange) -> CoachingAssessment: ...

    async def weekly_digest(self) -> CoachingDigest: ...

    async def generate_drill(self, dimension: str) -> Drill: ...


@runtime_checkable
class SpanValidator(Protocol):
    """Mechanical check that a citation's quote appears where it claims to.

    This is what converts "the prompt said to cite sources" into a property the system
    actually enforces.
    """

    def validate(self, meeting: Meeting, span: TranscriptSpan) -> bool: ...
