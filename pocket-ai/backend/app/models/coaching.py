"""Executive coaching assessments.

The governing constraint (docs/adr/0007-coaching-must-cite-evidence.md): no coaching
output without evidence from the user's own material. A dimension with no supporting
evidence is reported unscored rather than given an invented score.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .common import Cited, TranscriptSpan


class CoachingTrack(str, Enum):
    WRITTEN = "written"
    SPOKEN = "spoken"
    THOUGHT_LEADERSHIP = "thought_leadership"
    THOUGHT_DEVELOPMENT = "thought_development"


RUBRICS: dict[CoachingTrack, tuple[str, ...]] = {
    CoachingTrack.WRITTEN: (
        "clarity",
        "concision",
        "structure",
        "precision",
        "register",
        "hedging",
    ),
    CoachingTrack.SPOKEN: (
        "airtime",
        "filler_density",
        "hedging_under_pressure",
        "answer_directness",
        "interruption_pattern",
        "question_quality",
        "landing",
    ),
    CoachingTrack.THOUGHT_LEADERSHIP: (
        "point_of_view",
        "distinctiveness",
        "evidence",
        "consistency",
        "reach",
        "framing",
    ),
    CoachingTrack.THOUGHT_DEVELOPMENT: (
        "argument_structure",
        "steelmanning",
        "updating",
        "abstraction_control",
        "first_principles",
        "idea_maturity",
    ),
}


class DocumentRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    title: str
    excerpt: str


class RubricScore(BaseModel):
    """A per-dimension score with its evidence.

    ``score`` is ``None`` when the corpus held no evidence for this dimension in the
    window. Reporting that honestly is the point — inventing a number to complete the
    table destroys the credibility of every other score on it.
    """

    model_config = ConfigDict(frozen=True)

    dimension: str
    score: float | None = Field(default=None, ge=0.0, le=10.0)
    evidence: list[TranscriptSpan] = Field(default_factory=list)
    note: str | None = None

    @property
    def is_scored(self) -> bool:
        return self.score is not None


class DrillKind(str, Enum):
    REWRITE = "rewrite"
    CHALLENGE_RESPONSE = "challenge_response"
    STEELMAN = "steelman"
    COMPRESSION = "compression"
    SAME_SITUATION_REPLAY = "same_situation_replay"


class Drill(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: DrillKind
    dimension: str
    prompt: str
    source_spans: list[TranscriptSpan] = Field(default_factory=list)
    target_response: str | None = None
    completed_at: datetime | None = None


class CoachingAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessed_at: datetime
    track: CoachingTrack
    window_days: int = 90
    scores: dict[str, RubricScore] = Field(default_factory=dict)
    observations: list[Cited[str]] = Field(default_factory=list)
    drills: list[Drill] = Field(default_factory=list)
    delta_from_previous: dict[str, float] = Field(default_factory=dict)

    @property
    def scored_dimensions(self) -> list[str]:
        return [d for d, s in self.scores.items() if s.is_scored]

    @property
    def unscored_dimensions(self) -> list[str]:
        return [d for d, s in self.scores.items() if not s.is_scored]


class CoachingDigest(BaseModel):
    """One strength, one growth edge. Not a list of twelve findings.

    Behavior change comes from focused iteration; a comprehensive audit gets skimmed
    once and abandoned. The constraint is the feature.
    """

    generated_at: datetime
    strength: Cited[str] | None = None
    growth_edge: Cited[str] | None = None
    drill: Drill | None = None
    assessments: list[CoachingAssessment] = Field(default_factory=list)
