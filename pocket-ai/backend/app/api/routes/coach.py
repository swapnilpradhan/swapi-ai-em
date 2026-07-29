"""Executive coaching."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from ...models import (
    RUBRICS,
    CoachingAssessment,
    CoachingDigest,
    CoachingTrack,
    DateRange,
    Drill,
)
from ...services.registry import get_registry

router = APIRouter(prefix="/coach", tags=["coach"])


@router.get("/rubrics")
async def rubrics() -> dict[str, list[str]]:
    """The published rubrics.

    Visible to the user by design: hidden rubrics produce scores nobody trusts or can
    act on. See ADR-0007.
    """
    return {track.value: list(dims) for track, dims in RUBRICS.items()}


@router.get("/assess/{track}", response_model=CoachingAssessment)
async def assess(track: CoachingTrack, window_days: int = 90) -> CoachingAssessment:
    end = datetime.now(UTC)
    window = DateRange(start=end - timedelta(days=window_days), end=end)
    return await get_registry().coach.assess(track=track, window=window)


@router.get("/digest", response_model=CoachingDigest)
async def digest() -> CoachingDigest:
    """Weekly digest: one strength, one growth edge.

    Both may be absent when the corpus holds no evidence — an empty digest is the
    honest result, and padding it would be the failure mode.
    """
    return await get_registry().coach.weekly_digest()


@router.post("/drill/{dimension}", response_model=Drill)
async def drill(dimension: str) -> Drill:
    return await get_registry().coach.generate_drill(dimension)
