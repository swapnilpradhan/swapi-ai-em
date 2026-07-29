"""Derived meeting content: summaries, decisions, action items, mind maps.

Everything here is partial by design. One failing section must not lose the others.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .common import Cited, SectionStatus, TranscriptSpan


class Altitude(str, Enum):
    ONE_LINE = "one_line"
    EXECUTIVE = "executive"
    FULL_BRIEF = "full_brief"


class CommitmentType(str, Enum):
    """The distinction that keeps the action list trustworthy.

    ``HYPOTHETICAL`` items are recognized so they can be excluded — "someone should
    probably look at this" is not a commitment and must not become a task.
    """

    FIRM = "firm"
    ASSIGNED = "assigned"
    SOFT = "soft"
    HYPOTHETICAL = "hypothetical"


class ActionStatus(str, Enum):
    OPEN = "open"
    DONE = "done"
    DROPPED = "dropped"


class DueDate(BaseModel):
    """Parsed date plus what was actually said.

    ``parsed`` stays ``None`` when the phrase cannot be resolved — "next sprint" has no
    knowable boundary. A guessed date is a false deadline someone will plan around.
    """

    model_config = ConfigDict(frozen=True)

    raw: str
    parsed: date | None = None


class ActionItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str  # imperative, self-contained, no dangling pronouns
    owner_speaker_id: str | None = None
    owner_raw: str = ""  # what was said: "you", "the platform team"
    due: DueDate | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    commitment_type: CommitmentType = CommitmentType.SOFT
    spans: list[TranscriptSpan] = Field(default_factory=list)
    confirmed_by_user: bool = False
    status: ActionStatus = ActionStatus.OPEN

    @property
    def needs_confirmation(self) -> bool:
        return not self.confirmed_by_user and 0.5 <= self.confidence < 0.8

    @property
    def is_surfaceable(self) -> bool:
        if self.commitment_type is CommitmentType.HYPOTHETICAL:
            return False
        return self.confirmed_by_user or self.confidence >= 0.5


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    statement: str
    decided_by: list[str] = Field(default_factory=list)
    commits_to: str | None = None


class Risk(BaseModel):
    model_config = ConfigDict(frozen=True)

    statement: str
    raised_by: str | None = None
    severity: str | None = None


class Question(BaseModel):
    model_config = ConfigDict(frozen=True)

    statement: str
    raised_by: str | None = None


class Disagreement(BaseModel):
    """Where the room did not converge.

    Kept separate from decisions on purpose: this is often the most valuable content
    in a meeting and the thing generic summarizers smooth into false consensus.
    """

    model_config = ConfigDict(frozen=True)

    topic: str
    positions: dict[str, str] = Field(default_factory=dict)  # speaker -> position


class NodeType(str, Enum):
    TOPIC = "topic"
    DECISION = "decision"
    QUESTION = "question"
    TANGENT = "tangent"


class MindMapNode(BaseModel):
    label: str  # 2-6 words; a sentence here means the map is being used as prose
    node_type: NodeType = NodeType.TOPIC
    spans: list[TranscriptSpan] = Field(default_factory=list)
    children: list[MindMapNode] = Field(default_factory=list)

    def depth(self) -> int:
        return 1 + max((c.depth() for c in self.children), default=0)

    def node_count(self) -> int:
        return 1 + sum(c.node_count() for c in self.children)


class MindMap(BaseModel):
    root: MindMapNode
    rendered_mermaid: str = ""


class MeetingInsights(BaseModel):
    meeting_id: str
    prompt_version: str = "v1"
    generated_at: datetime | None = None

    one_line: Cited[str] | None = None
    executive_summary: Cited[str] | None = None
    full_brief: Cited[str] | None = None

    decisions: list[Cited[Decision]] = Field(default_factory=list)
    risks: list[Cited[Risk]] = Field(default_factory=list)
    open_questions: list[Cited[Question]] = Field(default_factory=list)
    disagreements: list[Cited[Disagreement]] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    mind_map: MindMap | None = None

    section_status: dict[str, SectionStatus] = Field(default_factory=dict)

    @property
    def surfaceable_actions(self) -> list[ActionItem]:
        return [a for a in self.action_items if a.is_surfaceable]

    @property
    def actions_needing_confirmation(self) -> list[ActionItem]:
        return [a for a in self.action_items if a.needs_confirmation]
