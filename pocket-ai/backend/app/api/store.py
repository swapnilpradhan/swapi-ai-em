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

    def put_meeting(self, meeting: Meeting) -> None:
        self.meetings[meeting.id] = meeting

    def get_meeting(self, meeting_id: str) -> Meeting | None:
        return self.meetings.get(meeting_id)

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
        self.library = VoiceprintLibrary()


@lru_cache
def get_store() -> MemoryStore:
    return MemoryStore()
