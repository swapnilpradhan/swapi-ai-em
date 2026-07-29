"""Grounded Q&A over the transcript corpus."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ...models import CitedAnswer, Filters, Scope
from ...services.registry import get_registry

router = APIRouter(prefix="/chat", tags=["chat"])


class AskRequest(BaseModel):
    question: str
    # Explicit, never inferred: guessing scope produces answers that are right about
    # the wrong meeting, which the user has almost no way to notice.
    scope: Scope = Scope.CORPUS
    meeting_id: str | None = None
    series_id: str | None = None
    speakers: list[str] = Field(default_factory=list)
    after: datetime | None = None
    before: datetime | None = None


@router.post("/ask", response_model=CitedAnswer)
async def ask(request: AskRequest) -> CitedAnswer:
    registry = get_registry()
    filters = Filters(
        meeting_id=request.meeting_id,
        series_id=request.series_id,
        speakers=request.speakers,
        after=request.after,
        before=request.before,
    )
    return await registry.chat.ask(request.question, scope=request.scope, filters=filters)
