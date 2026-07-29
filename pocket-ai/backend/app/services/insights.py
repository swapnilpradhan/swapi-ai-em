"""Summaries, decisions, action items, and mind maps.

Generation is two-pass by design: a fast tier extracts candidate claims with spans, a
mechanical validator drops the ones that don't hold up, and the reasoning tier
synthesizes only from what survived. The synthesizer never sees raw transcript, so it
cannot introduce ungrounded material.

See docs/adr/0004-grounded-generation.md and docs/capabilities/03-summaries-and-insights.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..core.config import Settings
from ..core.logging import get_logger
from ..models import (
    ActionItem,
    Cited,
    CommitmentType,
    Meeting,
    MeetingInsights,
    MindMap,
    MindMapNode,
    NodeType,
    SectionStatus,
    TranscriptSpan,
)
from .protocols import LLMService
from .validation import DefaultSpanValidator

log = get_logger(__name__)

PROMPT_VERSION = "v1"

# Phrases that mark a real commitment vs. an idle suggestion. Crude, and deliberately
# so — the stub's job is to exercise the CommitmentType distinction end to end, not to
# be the production classifier.
_FIRM_MARKERS = ("i'll ", "i will ", "i'm going to ")
_HYPOTHETICAL_MARKERS = ("someone should", "we could maybe", "it might be worth")


def render_mermaid(root: MindMapNode) -> str:
    """Render a mind map as Mermaid.

    Text-based so it is diffable, embeddable, and hand-editable. Labels are sanitized
    because parentheses and quotes break the parser, and a syntax error renders as a
    raw code block in the user's archive.
    """

    def clean(label: str) -> str:
        return label.replace("(", "").replace(")", "").replace('"', "").strip()

    lines = ["mindmap", f"  root(({clean(root.label)}))"]

    def walk(node: MindMapNode, depth: int) -> None:
        for child in node.children:
            indent = "  " * (depth + 1)
            label = clean(child.label)
            if child.node_type is NodeType.QUESTION:
                label = f"? {label}"
            elif child.node_type is NodeType.TANGENT:
                label = f"~ {label}"
            lines.append(f"{indent}{label}")
            walk(child, depth + 1)

    walk(root, 1)
    return "\n".join(lines)


class StubInsightsService:
    """Offline enrichment derived from transcript structure.

    Produces genuinely cited output — every span points at real segments and passes
    validation — so the grounding machinery is exercised without a model.
    """

    def __init__(self, settings: Settings, llm: LLMService) -> None:
        self.settings = settings
        self.llm = llm
        self.validator = DefaultSpanValidator()

    async def enrich(self, meeting: Meeting) -> MeetingInsights:
        segments = meeting.transcript.segments
        insights = MeetingInsights(
            meeting_id=meeting.id,
            prompt_version=PROMPT_VERSION,
            generated_at=datetime.now(UTC),
        )

        if not segments:
            insights.section_status = dict.fromkeys(
                ("summary", "action_items", "mind_map"), SectionStatus.SKIPPED
            )
            return insights

        first = segments[0]
        span = TranscriptSpan(
            meeting_id=meeting.id,
            segment_start=first.index,
            segment_end=first.index,
            quote=first.text,
        )

        insights.one_line = Cited[str](value=f"[stub] {meeting.title}", spans=[span])
        insights.executive_summary = Cited[str](
            value=(
                f"[stub] {len(segments)} segments across "
                f"{meeting.duration_seconds / 60:.0f} minutes. "
                "Configure ANTHROPIC_API_KEY for real synthesis."
            ),
            spans=[span],
        )
        insights.action_items = self._extract_actions(meeting)
        insights.mind_map = self._build_mind_map(meeting)

        insights.section_status = {
            "summary": SectionStatus.OK,
            "action_items": SectionStatus.OK,
            "mind_map": SectionStatus.OK,
        }

        # The validation pass runs even on stub output — if the stub can produce an
        # uncitable claim, so can the real thing.
        insights.action_items = [
            a for a in insights.action_items if self.validator.validate_all(meeting, a.spans)
        ]
        insights.one_line = self.validator.keep_if_valid(meeting, insights.one_line)
        insights.executive_summary = self.validator.keep_if_valid(
            meeting, insights.executive_summary
        )

        log.info(
            "enrich.stub",
            meeting_id=meeting.id,
            actions=len(insights.action_items),
        )
        return insights

    def _extract_actions(self, meeting: Meeting) -> list[ActionItem]:
        items: list[ActionItem] = []
        for seg in meeting.transcript.segments:
            lowered = seg.text.lower()
            if any(m in lowered for m in _HYPOTHETICAL_MARKERS):
                # Recognized so it can be excluded. A hypothetical must never become
                # a task — see docs/capabilities/05-action-items.md.
                continue
            if not any(m in lowered for m in _FIRM_MARKERS):
                continue
            items.append(
                ActionItem(
                    description=seg.text.strip(),
                    owner_speaker_id=seg.speaker_id,
                    owner_raw=seg.speaker_label or "",
                    confidence=0.85,
                    commitment_type=CommitmentType.FIRM,
                    spans=[
                        TranscriptSpan(
                            meeting_id=meeting.id,
                            segment_start=seg.index,
                            segment_end=seg.index,
                            quote=seg.text,
                        )
                    ],
                )
            )
        return items

    def _build_mind_map(self, meeting: Meeting) -> MindMap:
        segments = meeting.transcript.segments
        # One node per few segments, so depth and breadth constraints are exercised.
        children = [
            MindMapNode(
                label=" ".join(seg.text.split()[:4]) or "topic",
                node_type=NodeType.TOPIC,
                spans=[
                    TranscriptSpan(
                        meeting_id=meeting.id,
                        segment_start=seg.index,
                        segment_end=seg.index,
                        quote=seg.text,
                    )
                ],
            )
            for seg in segments[:5]
        ]
        root = MindMapNode(label=meeting.title, node_type=NodeType.TOPIC, children=children)
        return MindMap(root=root, rendered_mermaid=render_mermaid(root))


class LLMInsightsService:
    """Real enrichment via the two-pass grounded pipeline. Phase 2."""

    def __init__(self, settings: Settings, llm: LLMService) -> None:
        self.settings = settings
        self.llm = llm
        self.validator = DefaultSpanValidator()

    async def enrich(self, meeting: Meeting) -> MeetingInsights:
        raise NotImplementedError("Phase 2 — see docs/capabilities/03-summaries-and-insights.md")
