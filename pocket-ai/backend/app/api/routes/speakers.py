"""Speaker enrollment and manual tagging."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from ...models import (
    ConsentRecord,
    ConsentScope,
    Speaker,
    SpeakerSource,
    Voiceprint,
)
from ..store import get_store

router = APIRouter(prefix="/speakers", tags=["speakers"])


class EnrollRequest(BaseModel):
    display_name: str
    consent_method: str = "verbal_on_recording"
    consent_scope: ConsentScope = ConsentScope.RECORDING_ONLY
    relationship: str | None = None
    # Enrollment wants 3+ samples for robustness across mic conditions.
    embeddings: list[list[float]] = Field(default_factory=list)


@router.post("", response_model=Speaker, status_code=201)
async def enroll(request: EnrollRequest) -> Speaker:
    """Enroll a speaker.

    A voiceprint requires ``recording_and_voiceprint`` consent. The model enforces
    this, so an attempt to enroll under narrower consent fails here rather than
    silently storing biometric data — see docs/SECURITY_PRIVACY.md.
    """
    consent = ConsentRecord(
        granted_at=datetime.now(UTC),
        method=request.consent_method,
        scope=request.consent_scope,
    )
    voiceprint = (
        Voiceprint(embeddings=request.embeddings, enrolled_at=datetime.now(UTC))
        if request.embeddings
        else None
    )

    try:
        speaker = Speaker(
            display_name=request.display_name,
            relationship=request.relationship,
            consent=consent,
            voiceprint=voiceprint,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    get_store().enroll(speaker)
    return speaker


@router.get("", response_model=list[Speaker])
async def list_speakers() -> list[Speaker]:
    return get_store().library.speakers


@router.delete("/{speaker_id}/consent", response_model=Speaker)
async def revoke_consent(speaker_id: str) -> Speaker:
    """Revoke consent: drop the voiceprint and revert attribution everywhere.

    Revocation has to be a real path, not a policy statement.
    """
    store = get_store()
    speaker = store.library.by_id(speaker_id)
    if speaker is None:
        raise HTTPException(status_code=404, detail="speaker not found")

    revoked = speaker.revoke_consent(datetime.now(UTC))
    store.library = store.library.with_speaker(revoked)

    for meeting in store.meetings.values():
        meeting.turns = [
            t.model_copy(update={"speaker_id": None}) if t.speaker_id == speaker_id else t
            for t in meeting.turns
        ]
        meeting.transcript = meeting.transcript.model_copy(
            update={
                "segments": [
                    s.model_copy(update={"speaker_id": None, "speaker_source": None})
                    if s.speaker_id == speaker_id
                    else s
                    for s in meeting.transcript.segments
                ]
            }
        )

    return revoked


class TagRequest(BaseModel):
    meeting_id: str
    segment_indices: list[int]
    speaker_id: str


@router.post("/tag")
async def tag_segments(request: TagRequest) -> dict:
    """Manually tag segments.

    Manual tags are authoritative: identification skips them permanently, so a
    correction is never undone by a later model run.
    """
    store = get_store()
    meeting = store.get_meeting(request.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    if store.library.by_id(request.speaker_id) is None:
        raise HTTPException(status_code=404, detail="speaker not found")

    wanted = set(request.segment_indices)
    meeting.transcript = meeting.transcript.model_copy(
        update={
            "segments": [
                s.model_copy(
                    update={
                        "speaker_id": request.speaker_id,
                        "speaker_source": SpeakerSource.MANUAL,
                    }
                )
                if s.index in wanted
                else s
                for s in meeting.transcript.segments
            ]
        }
    )
    return {"tagged": len(wanted), "meeting_id": request.meeting_id}
