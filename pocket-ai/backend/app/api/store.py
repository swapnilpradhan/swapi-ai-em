"""In-memory store for Phase 0.

Postgres and Alembic land in Phase 2, when cross-meeting queries make real indexes
necessary. The Pydantic models stay the service-layer contract either way; the ORM is
a persistence detail underneath them. See docs/DATA_MODEL.md.
"""

from __future__ import annotations

from functools import lru_cache

from ..models import Meeting, MeetingInsights, Speaker, VoiceprintLibrary


class MemoryStore:
    def __init__(self) -> None:
        self.meetings: dict[str, Meeting] = {}
        self.insights: dict[str, MeetingInsights] = {}
        self.library = VoiceprintLibrary()
        # provider:external_id -> meeting_id. The cheap dedupe index: a webhook
        # redelivery can be resolved without fetching or hashing anything.
        self._by_external: dict[str, str] = {}

    def put_meeting(self, meeting: Meeting) -> None:
        self.meetings[meeting.id] = meeting
        if meeting.external_ref:
            self._by_external[meeting.external_ref.key] = meeting.id

    def get_meeting(self, meeting_id: str) -> Meeting | None:
        return self.meetings.get(meeting_id)

    def get_by_external(self, provider: str, external_id: str) -> Meeting | None:
        meeting_id = self._by_external.get(f"{provider}:{external_id}")
        return self.meetings.get(meeting_id) if meeting_id else None

    def is_current(self, provider: str, external_id: str, updated_at) -> bool:
        """Whether we already hold this recording at or beyond the given revision.

        Lets a redelivery short-circuit while still letting a genuine upstream edit
        through — the point of storing ``updated_at`` on the ref.
        """
        existing = self.get_by_external(provider, external_id)
        if existing is None or existing.external_ref is None:
            return False
        if updated_at is None or existing.external_ref.updated_at is None:
            return True  # no revision info either side: treat presence as current
        return existing.external_ref.updated_at >= updated_at

    def list_meetings(self) -> list[Meeting]:
        return sorted(self.meetings.values(), key=lambda m: m.occurred_at, reverse=True)

    def put_insights(self, insights: MeetingInsights) -> None:
        self.insights[insights.meeting_id] = insights

    def get_insights(self, meeting_id: str) -> MeetingInsights | None:
        return self.insights.get(meeting_id)

    def enroll(self, speaker: Speaker) -> VoiceprintLibrary:
        """Adding a speaker bumps ``library.version``.

        That version participates in the identification cache key, which is what makes
        retroactive naming across past meetings cheap — see ADR-0003.
        """
        self.library = self.library.with_speaker(speaker)
        return self.library

    def speaker_names(self) -> dict[str, str]:
        return {s.id: s.display_name for s in self.library.speakers}

    def clear(self) -> None:
        self.meetings.clear()
        self.insights.clear()
        self._by_external.clear()
        self.library = VoiceprintLibrary()


@lru_cache
def get_store() -> MemoryStore:
    return MemoryStore()
