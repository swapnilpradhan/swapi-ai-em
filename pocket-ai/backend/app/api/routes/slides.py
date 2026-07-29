"""Deck generation.

Structure and rendering are separate endpoints on purpose. The outline is the artifact
of record and must be reviewable before anything is rendered — see ADR-0006.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...agents.slide_builder import (
    DeckStructure,
    HouseStyle,
    MECEViolation,
    render_outline,
    validate_mece,
)
from ...services.registry import get_registry
from ..store import get_store

router = APIRouter(prefix="/slides", tags=["slides"])


class StructureRequest(BaseModel):
    meeting_id: str
    style: HouseStyle = HouseStyle.NEUTRAL
    audience: str = "leadership"


class StructureResponse(BaseModel):
    structure: DeckStructure
    outline_markdown: str
    title_thread: list[str]
    mece_violations: list[MECEViolation]
    ready_to_render: bool


@router.post("/structure", response_model=StructureResponse)
async def build_structure(request: StructureRequest) -> StructureResponse:
    """Produce the reviewable argument structure. Rendering is a separate call."""
    store = get_store()
    meeting = store.get_meeting(request.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")

    registry = get_registry()
    try:
        structure = await registry.slides.build_structure(meeting, style=request.style)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    structure.audience = request.audience
    violations = validate_mece(structure)

    return StructureResponse(
        structure=structure,
        outline_markdown=render_outline(structure),
        title_thread=structure.title_thread(),
        mece_violations=violations,
        ready_to_render=not violations,
    )


class RenderRequest(BaseModel):
    structure: DeckStructure
    force: bool = False


@router.post("/render")
async def render(request: RenderRequest) -> dict:
    """Render an approved structure.

    Refuses on MECE violations unless explicitly forced — rendering a broken argument
    is the expensive mistake this pipeline exists to prevent.
    """
    violations = validate_mece(request.structure)
    if violations and not request.force:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "structure failed MECE validation; fix or pass force=true",
                "violations": [v.model_dump() for v in violations],
            },
        )

    registry = get_registry()
    content = await registry.slides.render(request.structure)
    return {
        "size_bytes": len(content),
        "preview": content.decode("utf-8", errors="replace")[:2000],
        "forced": bool(violations),
    }
