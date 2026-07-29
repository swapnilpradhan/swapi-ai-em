"""Executive coaching.

The governing constraint: no output without evidence from the user's own material.
A dimension with no supporting evidence in the window is reported unscored rather
than given an invented number — see docs/adr/0007-coaching-must-cite-evidence.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..core.config import Settings
from ..core.logging import get_logger
from ..models import (
    RUBRICS,
    CoachingAssessment,
    CoachingDigest,
    CoachingTrack,
    DateRange,
    Drill,
    DrillKind,
    RubricScore,
)
from ..services.protocols import LLMService

log = get_logger(__name__)

# Below this, a baseline says more about sampling noise than about the person.
MIN_CORPUS_MEETINGS = 10

# Qualifiers whose density under challenge is the flagship spoken-track signal.
HEDGE_MARKERS = (
    "probably",
    "i think maybe",
    "it could be that",
    "sort of",
    "kind of",
    "i guess",
    "perhaps",
)

FILLER_MARKERS = ("um", "uh", "like", "you know")


class InsufficientCorpus(RuntimeError):
    """Raised when there is not enough material for a meaningful assessment."""


def hedge_density(text: str) -> float:
    """Hedges per 100 words. Compare baseline against post-challenge windows."""
    words = text.split()
    if not words:
        return 0.0
    lowered = text.lower()
    hedges = sum(lowered.count(m) for m in HEDGE_MARKERS)
    return hedges / len(words) * 100


def filler_density(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0
    lowered = [w.strip(".,!?").lower() for w in words]
    return sum(1 for w in lowered if w in FILLER_MARKERS) / len(words) * 100


class StubCoachService:
    """Offline coach that models the honest-reporting behaviour.

    It scores nothing, because with no corpus there is no evidence — which is exactly
    what the real implementation must do when a dimension has no support. Every
    dimension comes back unscored with a stated reason.
    """

    def __init__(self, settings: Settings, llm: LLMService) -> None:
        self.settings = settings
        self.llm = llm

    async def assess(self, *, track: CoachingTrack, window: DateRange) -> CoachingAssessment:
        dimensions = RUBRICS[track]
        return CoachingAssessment(
            assessed_at=datetime.now(UTC),
            track=track,
            window_days=(window.end - window.start).days,
            scores={
                d: RubricScore(
                    dimension=d,
                    score=None,
                    note="no corpus evidence in window",
                )
                for d in dimensions
            },
        )

    async def weekly_digest(self) -> CoachingDigest:
        # One strength, one growth edge — and with no evidence, neither. Padding the
        # digest to look useful is the failure mode this design exists to prevent.
        return CoachingDigest(generated_at=datetime.now(UTC))

    async def generate_drill(self, dimension: str) -> Drill:
        return Drill(
            kind=DrillKind.REWRITE,
            dimension=dimension,
            prompt=(
                "[stub] Drills are built from your own recorded moments. "
                "Process some meetings first."
            ),
        )


class CorpusCoachService:
    """Real coach, scoring against the corpus. Phase 4.

    Requires at least MIN_CORPUS_MEETINGS of processed, attributed material before a
    baseline is meaningful.
    """

    def __init__(self, settings: Settings, llm: LLMService, retrieval) -> None:
        self.settings = settings
        self.llm = llm
        self.retrieval = retrieval

    async def assess(self, *, track: CoachingTrack, window: DateRange) -> CoachingAssessment:
        raise NotImplementedError("Phase 4 — see docs/capabilities/08-executive-coach.md")

    async def weekly_digest(self) -> CoachingDigest:
        raise NotImplementedError("Phase 4 — see docs/capabilities/08-executive-coach.md")

    async def generate_drill(self, dimension: str) -> Drill:
        raise NotImplementedError("Phase 4 — see docs/capabilities/08-executive-coach.md")
