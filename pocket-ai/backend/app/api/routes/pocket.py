"""Pocket API sync — manual pulls and history backfill."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from ...core.config import Backend, get_settings
from ...services.registry import get_registry
from ...services.sync import IngestOutcome, backfill, ingest_recording
from ..store import get_store

router = APIRouter(prefix="/pocket", tags=["pocket"])


class PullRequest(BaseModel):
    recording_id: str
    # Re-process even when we already hold the current revision — for prompt changes
    # and for recovering from a bad earlier run.
    force: bool = False


class PullResponse(BaseModel):
    outcome: IngestOutcome
    recording_id: str
    meeting_id: str | None = None
    reason: str | None = None


@router.post("/pull", response_model=PullResponse)
async def pull(request: PullRequest) -> PullResponse:
    """Fetch one recording synchronously. Same path a webhook takes."""
    result = await ingest_recording(
        request.recording_id, get_registry(), get_store(), force=request.force
    )
    return PullResponse(
        outcome=result.outcome,
        recording_id=result.recording_id,
        meeting_id=result.meeting_id,
        reason=result.reason,
    )


class BackfillRequest(BaseModel):
    page_size: int = Field(default=50, ge=1, le=200)
    max_recordings: int = Field(default=500, ge=1, le=5000)
    run_in_background: bool = True


@router.post("/backfill")
async def run_backfill(request: BackfillRequest, background: BackgroundTasks) -> dict:
    """Walk recording history through the ingest path.

    Backgrounded by default — a first run against years of recordings takes far longer
    than any sensible HTTP timeout.
    """
    registry, store = get_registry(), get_store()

    if request.run_in_background:
        background.add_task(
            backfill,
            registry,
            store,
            limit=request.page_size,
            max_recordings=request.max_recordings,
        )
        return {"status": "started", "max_recordings": request.max_recordings}

    results = await backfill(
        registry, store, limit=request.page_size, max_recordings=request.max_recordings
    )
    counts: dict[str, int] = {}
    for result in results:
        counts[result.outcome.value] = counts.get(result.outcome.value, 0) + 1
    return {"status": "complete", "total": len(results), "outcomes": counts}


@router.get("/status")
async def status() -> dict:
    settings = get_settings()
    return {
        "backend": settings.pocket_backend.value,
        "configured": settings.pocket_backend is Backend.REAL,
        "base_url": settings.pocket_api_base_url,
        "webhook_configured": settings.webhook_configured,
        "note": (
            "Endpoint paths and field names are unverified against Pocket's spec; "
            "they are centralized in backend/app/services/pocket.py (PocketRoutes)."
        ),
    }
