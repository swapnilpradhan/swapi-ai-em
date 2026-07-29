"""Meeting ingest and retrieval."""

from __future__ import annotations

import base64
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...models import AudioQuality, Meeting, MeetingInsights
from ...services.artifacts import build_artifacts
from ...services.ingest import build_meeting
from ...services.pipeline import process
from ...services.registry import get_registry
from ..store import get_store

router = APIRouter(prefix="/meetings", tags=["meetings"])


class IngestRequest(BaseModel):
    title: str
    occurred_at: datetime
    duration_seconds: float = Field(gt=0)
    raw_transcript: str
    audio_base64: str = ""
    original_filename: str = "audio.m4a"
    series_id: str | None = None
    snr_db: float | None = None
    clipping_ratio: float = 0.0


class IngestResponse(BaseModel):
    meeting: Meeting
    insights: MeetingInsights | None
    stub_backends: list[str]


@router.post("", response_model=IngestResponse, status_code=201)
async def ingest(request: IngestRequest) -> IngestResponse:
    registry = get_registry()
    store = get_store()

    try:
        audio = base64.b64decode(request.audio_base64) if request.audio_base64 else b""
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid audio_base64: {exc}") from exc

    if not audio:
        # Identity is the audio content hash; without audio, hash the transcript so
        # re-ingesting the same material still deduplicates.
        audio = request.raw_transcript.encode("utf-8")

    meeting = build_meeting(
        title=request.title,
        occurred_at=request.occurred_at,
        audio_bytes=audio,
        raw_transcript=request.raw_transcript,
        duration_seconds=request.duration_seconds,
        original_filename=request.original_filename,
        series_id=request.series_id,
        quality=AudioQuality(snr_db=request.snr_db, clipping_ratio=request.clipping_ratio),
    )

    meeting, insights = await process(meeting, registry, library=store.library)
    store.put_meeting(meeting)
    if insights is not None:
        store.put_insights(insights)

    return IngestResponse(meeting=meeting, insights=insights, stub_backends=registry.stub_backends)


@router.get("", response_model=list[Meeting])
async def list_meetings() -> list[Meeting]:
    return get_store().list_meetings()


@router.get("/{meeting_id}", response_model=Meeting)
async def get_meeting(meeting_id: str) -> Meeting:
    meeting = get_store().get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting


@router.get("/{meeting_id}/insights", response_model=MeetingInsights)
async def get_insights(meeting_id: str) -> MeetingInsights:
    insights = get_store().get_insights(meeting_id)
    if insights is None:
        raise HTTPException(status_code=404, detail="insights not found")
    return insights


@router.get("/{meeting_id}/artifacts")
async def list_artifacts(meeting_id: str) -> dict:
    store = get_store()
    meeting = store.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")

    artifacts = build_artifacts(
        meeting, store.get_insights(meeting_id), speaker_names=store.speaker_names()
    )
    return {
        "folder_name": meeting.folder_name,
        "artifacts": [
            {
                "kind": a.kind.value,
                "filename": a.filename,
                "size_bytes": len(a.content),
                "content_hash": a.content_hash,
            }
            for a in artifacts
        ],
    }
