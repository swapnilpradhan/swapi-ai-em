"""Speakers, voiceprints, and consent.

Consent is a required field on ``Speaker`` rather than a flag stored elsewhere. Making
it structurally impossible to enroll a voiceprint without a consent record is the point
— see docs/SECURITY_PRIVACY.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import TranscriptSpan


class ConsentScope(str, Enum):
    """Agreeing to be recorded is not agreeing to a stored biometric identifier.

    The two are separate permissions and the system defaults to the narrower one.
    """

    RECORDING_ONLY = "recording_only"
    RECORDING_AND_VOICEPRINT = "recording_and_voiceprint"


class ConsentRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    granted_at: datetime
    method: str  # verbal_on_recording | written | meeting_policy
    scope: ConsentScope = ConsentScope.RECORDING_ONLY
    evidence_span: TranscriptSpan | None = None
    revoked_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    @property
    def permits_voiceprint(self) -> bool:
        return self.is_active and self.scope is ConsentScope.RECORDING_AND_VOICEPRINT


class Voiceprint(BaseModel):
    """Speaker embeddings. Never leaves local infrastructure.

    Multiple samples improve robustness across microphone conditions and vocal
    variation; three is the working minimum.
    """

    model_config = ConfigDict(frozen=True)

    embeddings: list[list[float]] = Field(min_length=1)
    enrolled_at: datetime
    library_version: int = 1

    @property
    def sample_count(self) -> int:
        return len(self.embeddings)


class Speaker(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    relationship: str | None = None
    consent: ConsentRecord
    voiceprint: Voiceprint | None = None

    @model_validator(mode="after")
    def _voiceprint_requires_consent(self) -> Speaker:
        if self.voiceprint is not None and not self.consent.permits_voiceprint:
            raise ValueError(
                f"cannot hold a voiceprint for {self.display_name!r}: consent scope is "
                f"{self.consent.scope.value!r} and must be "
                f"{ConsentScope.RECORDING_AND_VOICEPRINT.value!r}"
            )
        return self

    def revoke_consent(self, at: datetime) -> Speaker:
        """Drop the voiceprint and mark consent revoked.

        Reverting this speaker's turns across stored meetings is the caller's job —
        this only handles the speaker record itself.
        """
        return self.model_copy(
            update={
                "voiceprint": None,
                "consent": self.consent.model_copy(update={"revoked_at": at}),
            }
        )


class VoiceprintLibrary(BaseModel):
    """The enrolled speaker set.

    ``version`` participates in the identification cache key, so enrolling a new
    speaker invalidates identification — and only identification — across affected
    meetings. That is what makes retroactive naming cheap. See ADR-0003.
    """

    speakers: list[Speaker] = Field(default_factory=list)
    version: int = 1

    def enrolled(self) -> list[Speaker]:
        return [s for s in self.speakers if s.voiceprint is not None]

    def by_id(self, speaker_id: str) -> Speaker | None:
        return next((s for s in self.speakers if s.id == speaker_id), None)

    def with_speaker(self, speaker: Speaker) -> VoiceprintLibrary:
        others = [s for s in self.speakers if s.id != speaker.id]
        return VoiceprintLibrary(speakers=[*others, speaker], version=self.version + 1)
