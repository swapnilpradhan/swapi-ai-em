"""Consulting-grade deck construction.

Structure is produced, validated, and made reviewable before anything is rendered. A
beautiful deck with an incoherent argument is worse than a text document, because the
polish hides the incoherence until someone asks a question in the room.

See docs/adr/0006-slides-structure-before-render.md.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from ..core.config import Settings
from ..core.logging import get_logger
from ..models import Cited, Meeting, TranscriptSpan
from ..services.protocols import LLMService

log = get_logger(__name__)

MIN_ARGUMENTS = 2
MAX_ARGUMENTS = 5


class HouseStyle(str, Enum):
    """Structural idioms plus generic professional styling.

    Firm logos, proprietary templates, and trade dress are deliberately excluded —
    they belong to those firms, and imitating them misrepresents the deck's origin.
    """

    MCKINSEY = "mckinsey"
    KPMG = "kpmg"
    DELOITTE = "deloitte"
    NEUTRAL = "neutral"


class BodyKind(str, Enum):
    BULLETS = "bullets"
    CHART = "chart"
    TABLE = "table"
    QUOTE = "quote"
    COMPARISON = "comparison"


class SlideBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: BodyKind = BodyKind.BULLETS
    content: list[str] = Field(default_factory=list)


class Slide(BaseModel):
    action_title: str  # a full-sentence assertion, not a label
    body: SlideBody = Field(default_factory=SlideBody)
    so_what: str = ""  # empty means the slide has not earned its place
    spans: list[TranscriptSpan] = Field(default_factory=list)


class Argument(BaseModel):
    assertion: str
    slides: list[Slide] = Field(default_factory=list)
    spans: list[TranscriptSpan] = Field(default_factory=list)


class DeckStructure(BaseModel):
    governing_thought: Cited[str]
    audience: str = "leadership"
    style: HouseStyle = HouseStyle.NEUTRAL
    arguments: list[Argument] = Field(default_factory=list)
    appendix: list[Slide] = Field(default_factory=list)

    def all_slides(self) -> list[Slide]:
        return [s for a in self.arguments for s in a.slides]

    def title_thread(self) -> list[str]:
        """The action titles in order.

        Reading these alone must give the complete argument. Extracting them is the
        cheapest way to check whether the deck actually argues anything.
        """
        return [s.action_title for s in self.all_slides()]


class MECEViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str  # "overlap" | "coverage" | "count"
    detail: str


def validate_mece(structure: DeckStructure) -> list[MECEViolation]:
    """Mechanical structural checks on the argument decomposition.

    Catching a broken decomposition here is nearly free; catching it after rendering
    means redoing the deck.
    """
    violations: list[MECEViolation] = []
    args = structure.arguments

    if not MIN_ARGUMENTS <= len(args) <= MAX_ARGUMENTS:
        violations.append(
            MECEViolation(
                kind="count",
                detail=(
                    f"{len(args)} supporting arguments; expected "
                    f"{MIN_ARGUMENTS}-{MAX_ARGUMENTS}. More than {MAX_ARGUMENTS} "
                    "usually means the decomposition is wrong, not that the topic is complex."
                ),
            )
        )

    # Mutually exclusive: two arguments citing the same evidence are not distinct claims.
    for i, a in enumerate(args):
        for b in args[i + 1 :]:
            shared = [s for s in a.spans if any(s.overlaps(o) for o in b.spans)]
            if shared:
                violations.append(
                    MECEViolation(
                        kind="overlap",
                        detail=(
                            f"{a.assertion!r} and {b.assertion!r} cite overlapping "
                            f"evidence ({len(shared)} span(s))"
                        ),
                    )
                )

    # Collectively exhaustive: an argument with no evidence covers nothing.
    for a in args:
        if not a.spans:
            violations.append(
                MECEViolation(
                    kind="coverage",
                    detail=f"{a.assertion!r} cites no evidence",
                )
            )

    return violations


def render_outline(structure: DeckStructure) -> str:
    """The reviewable Markdown outline — the artifact of record.

    The .pptx is a projection of this. Restructuring costs one regeneration here
    instead of a re-render.
    """
    lines = [
        f"# {structure.governing_thought.value}",
        "",
        f"*Audience:* {structure.audience} · *Style:* {structure.style.value}",
        "",
        "## Argument",
        "",
    ]
    for i, arg in enumerate(structure.arguments, 1):
        lines.append(f"### {i}. {arg.assertion}")
        lines.append("")
        for slide in arg.slides:
            lines.append(f"- **{slide.action_title}**")
            for item in slide.body.content:
                lines.append(f"  - {item}")
            if slide.so_what:
                lines.append(f"  - *So what:* {slide.so_what}")
            lines.append("")

    lines.extend(["## Title thread", ""])
    lines.extend(f"{i}. {t}" for i, t in enumerate(structure.title_thread(), 1))
    lines.append("")
    lines.append("*Read the thread above on its own. If it does not form a complete")
    lines.append("argument, the deck does not either.*")
    return "\n".join(lines)


class StubSlideBuilder:
    """Offline builder producing a structurally valid single-argument deck.

    Enough to exercise MECE validation, the outline renderer, and the review gate.
    """

    def __init__(self, settings: Settings, llm: LLMService) -> None:
        self.settings = settings
        self.llm = llm

    async def build_structure(
        self, meeting: Meeting, *, style: HouseStyle = HouseStyle.NEUTRAL
    ) -> DeckStructure:
        segments = meeting.transcript.segments
        if not segments:
            raise ValueError("cannot build a deck from an empty transcript")

        spans = [
            TranscriptSpan(
                meeting_id=meeting.id,
                segment_start=seg.index,
                segment_end=seg.index,
                quote=seg.text,
            )
            for seg in segments[:3]
        ]

        return DeckStructure(
            governing_thought=Cited[str](
                value=f"[stub] Governing thought for {meeting.title}",
                spans=spans[:1],
            ),
            style=style,
            arguments=[
                Argument(
                    assertion=f"[stub] Supporting argument {i + 1}",
                    spans=[span],
                    slides=[
                        Slide(
                            action_title=f"[stub] Assertion {i + 1} proven by the discussion",
                            body=SlideBody(content=[span.quote[:120]]),
                            so_what="[stub] implication",
                            spans=[span],
                        )
                    ],
                )
                for i, span in enumerate(spans[:2])
            ],
        )

    async def render(self, structure: DeckStructure) -> bytes:
        """Stub render emits the outline. Real .pptx rendering is Phase 3."""
        return render_outline(structure).encode("utf-8")
