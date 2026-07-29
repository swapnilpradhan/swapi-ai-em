"""Render meeting data into the artifacts that land in Drive.

Every format here opens without this application — Markdown, Mermaid, JSON. That is
the constraint ADR-0002 imposes: assume the app is gone in five years and someone is
looking at the folder.
"""

from __future__ import annotations

from ..models import (
    Artifact,
    ArtifactKind,
    Meeting,
    MeetingInsights,
)
from .ingest import content_hash


def _artifact(kind: ArtifactKind, text: str) -> Artifact:
    data = text.encode("utf-8")
    return Artifact(kind=kind, content=data, content_hash=content_hash(data))


def render_transcript_md(meeting: Meeting, speaker_names: dict[str, str] | None = None) -> str:
    names = speaker_names or {}
    lines = [
        f"# {meeting.title}",
        "",
        f"*{meeting.occurred_at:%Y-%m-%d %H:%M}* · {meeting.duration_seconds / 60:.0f} min",
        "",
    ]

    if not meeting.transcript.is_attributed:
        lines.extend(
            [
                "> Speaker attribution is not available for this recording.",
                "",
            ]
        )

    current: str | None = None
    for seg in meeting.transcript.segments:
        who = names.get(seg.speaker_id or "", seg.speaker_label or "")
        if who and who != current:
            lines.extend(["", f"**{who}**", ""])
            current = who
        stamp = f"{seg.start_ms // 60000:02d}:{(seg.start_ms // 1000) % 60:02d}"
        lines.append(f"`{stamp}` {seg.text}")

    return "\n".join(lines) + "\n"


def render_summary_md(meeting: Meeting, insights: MeetingInsights) -> str:
    lines = [f"# Summary — {meeting.title}", "", f"*{meeting.occurred_at:%Y-%m-%d}*", ""]

    if insights.one_line:
        lines.extend([f"**{insights.one_line.value}**", ""])

    if insights.executive_summary:
        lines.extend([insights.executive_summary.value, ""])

    if insights.decisions:
        lines.extend(["## Decisions", ""])
        lines.extend(f"- {d.value.statement}" for d in insights.decisions)
        lines.append("")

    if insights.disagreements:
        # Surfaced prominently: where the room did not converge is often the most
        # valuable content, and the easiest thing to lose.
        lines.extend(["## Where the room did not converge", ""])
        for d in insights.disagreements:
            lines.append(f"- **{d.value.topic}**")
            lines.extend(f"  - {who}: {pos}" for who, pos in d.value.positions.items())
        lines.append("")

    if insights.risks:
        lines.extend(["## Risks", ""])
        lines.extend(f"- {r.value.statement}" for r in insights.risks)
        lines.append("")

    if insights.open_questions:
        lines.extend(["## Open questions", ""])
        lines.extend(f"- {q.value.statement}" for q in insights.open_questions)
        lines.append("")

    if not insights.decisions:
        lines.extend(["*No decisions were reached in this meeting.*", ""])

    return "\n".join(lines) + "\n"


def render_action_items_md(insights: MeetingInsights, names: dict[str, str] | None = None) -> str:
    names = names or {}
    lines = ["# Action items", ""]

    surfaceable = insights.surfaceable_actions
    if not surfaceable:
        lines.append("*No commitments were made in this meeting.*")
        return "\n".join(lines) + "\n"

    for item in surfaceable:
        owner = names.get(item.owner_speaker_id or "", item.owner_raw) or "unassigned"
        due = item.due.raw if item.due else "no date"
        lines.append(
            f"- [ ] **{owner}** — {item.description} *({due}, {item.commitment_type.value})*"
        )

    pending = insights.actions_needing_confirmation
    if pending:
        lines.extend(["", "## Confirm these", ""])
        lines.extend(f"- {i.description} *(confidence {i.confidence:.2f})*" for i in pending)

    return "\n".join(lines) + "\n"


def render_mind_map_md(meeting: Meeting, insights: MeetingInsights) -> str:
    if insights.mind_map is None:
        return f"# Mind map — {meeting.title}\n\n*Not generated.*\n"
    return (
        f"# Mind map — {meeting.title}\n\n```mermaid\n{insights.mind_map.rendered_mermaid}\n```\n"
    )


def build_artifacts(
    meeting: Meeting,
    insights: MeetingInsights | None = None,
    *,
    speaker_names: dict[str, str] | None = None,
) -> list[Artifact]:
    """Everything derivable from a meeting, ready for export."""
    artifacts = [
        _artifact(ArtifactKind.TRANSCRIPT_MD, render_transcript_md(meeting, speaker_names)),
        _artifact(
            ArtifactKind.TRANSCRIPT_JSON,
            meeting.transcript.model_dump_json(indent=2),
        ),
    ]

    if insights is not None:
        artifacts.extend(
            [
                _artifact(ArtifactKind.SUMMARY, render_summary_md(meeting, insights)),
                _artifact(
                    ArtifactKind.ACTION_ITEMS, render_action_items_md(insights, speaker_names)
                ),
                _artifact(ArtifactKind.MIND_MAP, render_mind_map_md(meeting, insights)),
            ]
        )

    return artifacts
