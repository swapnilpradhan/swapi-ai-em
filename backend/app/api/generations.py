"""
API routes for content generation, library browsing, and HTML preview.
"""
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import Generation, GenerationStep, AuditLog
from app.db.schemas import (
    GenerateRequest, GenerationOut, GenerationListOut,
    GenerationStepOut, PaginatedResponse,
)

logger = logging.getLogger("api.generations")
router = APIRouter(prefix="/api/generations", tags=["generations"])


@router.post("", response_model=GenerationOut, status_code=201)
async def create_generation(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Trigger a new content generation and persist results to DB."""
    from app.agents.topic_breakdown_agent import TopicBreakdownAgent
    from app.agents.research_agent import ResearchAgent
    from app.agents.html_generation_agent import HTMLGenerationAgent

    gen_id = uuid.uuid4()
    correlation_id = str(gen_id)

    # Create generation record
    gen = Generation(
        id=gen_id,
        topic=req.topic,
        workflow_type=req.workflow_type,
        status="running",
    )
    db.add(gen)
    await db.flush()

    # Audit: generation started
    db.add(AuditLog(
        event_type="generation_started",
        correlation_id=correlation_id,
        payload={"topic": req.topic, "workflow_type": req.workflow_type},
    ))
    await db.flush()

    t0 = time.time()
    steps_meta = [
        {"step": 0, "agent": "topic_breakdown_agent", "task": "topic_analysis"},
        {"step": 1, "agent": "research_agent", "task": "research_planning"},
        {"step": 2, "agent": "html_generation_agent", "task": "html_creation"},
    ]

    # Pre-create step rows
    step_rows = []
    for sm in steps_meta:
        row = GenerationStep(
            generation_id=gen_id,
            step_number=sm["step"],
            agent_id=sm["agent"],
            task_type=sm["task"],
            status="pending",
        )
        db.add(row)
        step_rows.append(row)
    await db.flush()

    try:
        # ── Step 0: Topic Breakdown ──
        step_rows[0].status = "running"
        step_rows[0].started_at = datetime.now(timezone.utc)
        await db.flush()

        tba = TopicBreakdownAgent()
        tb_result = await tba.process_task({"topic": req.topic})
        context_id = tb_result["context_id"]

        step_rows[0].status = "completed"
        step_rows[0].completed_at = datetime.now(timezone.utc)
        step_rows[0].duration_ms = (time.time() - t0) * 1000
        step_rows[0].result_summary = {
            "context_id": context_id,
            "subtopics_count": len(tb_result.get("subtopics", [])),
            "subtopics": [s.get("title", s.get("name", "")) for s in tb_result.get("subtopics", [])],
        }
        await db.flush()

        db.add(AuditLog(
            event_type="step_completed", agent_id="topic_breakdown_agent",
            correlation_id=correlation_id,
            payload={"step": 0, "context_id": context_id},
        ))
        await db.flush()

        # ── Step 1: Research ──
        t1 = time.time()
        step_rows[1].status = "running"
        step_rows[1].started_at = datetime.now(timezone.utc)
        await db.flush()

        ra = ResearchAgent()
        ra_result = await ra.process_task({"context_id": context_id})
        content_structure = ra_result["content_structure"]
        style_guide = ra_result["style_guide"]

        step_rows[1].status = "completed"
        step_rows[1].completed_at = datetime.now(timezone.utc)
        step_rows[1].duration_ms = (time.time() - t1) * 1000
        step_rows[1].result_summary = {
            "sections_count": len(content_structure.get("sections", [])),
            "has_style_guide": True,
        }
        await db.flush()

        db.add(AuditLog(
            event_type="step_completed", agent_id="research_agent",
            correlation_id=correlation_id,
            payload={"step": 1, "sections": len(content_structure.get("sections", []))},
        ))
        await db.flush()

        # ── Step 2: HTML Generation ──
        t2 = time.time()
        step_rows[2].status = "running"
        step_rows[2].started_at = datetime.now(timezone.utc)
        await db.flush()

        hga = HTMLGenerationAgent()
        hga_result = await hga.process_task({
            "topic": req.topic,
            "content_structure": content_structure,
            "style_guide": style_guide,
        })
        file_path = hga_result["file_path"]

        step_rows[2].status = "completed"
        step_rows[2].completed_at = datetime.now(timezone.utc)
        step_rows[2].duration_ms = (time.time() - t2) * 1000
        step_rows[2].result_summary = {"file_path": file_path}
        await db.flush()

        # Read generated HTML and persist
        html_content = ""
        try:
            import aiofiles
            full_path = file_path
            if not file_path.startswith("/"):
                import os
                full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), file_path)
            async with aiofiles.open(full_path, "r") as f:
                html_content = await f.read()
        except Exception as e:
            logger.warning(f"Could not read generated HTML: {e}")

        total_ms = (time.time() - t0) * 1000
        gen.status = "completed"
        gen.html_content = html_content
        gen.file_path = file_path
        gen.total_duration_ms = total_ms
        gen.metadata_ = {
            "subtopics_count": len(tb_result.get("subtopics", [])),
            "sections_count": len(content_structure.get("sections", [])),
        }
        await db.flush()

        db.add(AuditLog(
            event_type="generation_completed",
            correlation_id=correlation_id,
            payload={"total_duration_ms": total_ms, "file_path": file_path},
        ))
        await db.flush()

    except Exception as exc:
        total_ms = (time.time() - t0) * 1000
        gen.status = "failed"
        gen.error = str(exc)
        gen.total_duration_ms = total_ms

        # Mark any running steps as failed
        for sr in step_rows:
            if sr.status in ("pending", "running"):
                sr.status = "failed"
                sr.error = str(exc)
                sr.completed_at = datetime.now(timezone.utc)

        db.add(AuditLog(
            event_type="generation_failed",
            correlation_id=correlation_id,
            payload={"error": str(exc), "total_duration_ms": total_ms},
        ))
        await db.flush()

        logger.error(f"Generation failed for '{req.topic}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    # Reload with steps for response
    result = await db.execute(
        select(Generation).options(selectinload(Generation.steps)).where(Generation.id == gen_id)
    )
    return result.scalar_one()


@router.get("", response_model=PaginatedResponse)
async def list_generations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    topic: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all generations with pagination and filters."""
    query = select(Generation)
    count_query = select(func.count(Generation.id))

    if status:
        query = query.where(Generation.status == status)
        count_query = count_query.where(Generation.status == status)
    if topic:
        query = query.where(Generation.topic.ilike(f"%{topic}%"))
        count_query = count_query.where(Generation.topic.ilike(f"%{topic}%"))

    total = (await db.execute(count_query)).scalar() or 0
    pages = max(1, (total + page_size - 1) // page_size)

    query = query.order_by(desc(Generation.created_at)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[GenerationListOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{generation_id}", response_model=GenerationOut)
async def get_generation(generation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single generation with all steps."""
    result = await db.execute(
        select(Generation).options(selectinload(Generation.steps)).where(Generation.id == generation_id)
    )
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")
    return gen


@router.get("/{generation_id}/html")
async def get_generation_html(generation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get raw HTML content for iframe preview."""
    result = await db.execute(select(Generation).where(Generation.id == generation_id))
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")
    if not gen.html_content:
        raise HTTPException(status_code=404, detail="No HTML content available")
    return HTMLResponse(content=gen.html_content)


@router.get("/{generation_id}/steps", response_model=list[GenerationStepOut])
async def get_generation_steps(generation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get step-by-step breakdown with timing."""
    result = await db.execute(
        select(GenerationStep)
        .where(GenerationStep.generation_id == generation_id)
        .order_by(GenerationStep.step_number)
    )
    return result.scalars().all()


@router.delete("/{generation_id}", status_code=204)
async def delete_generation(generation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a generation and its steps."""
    result = await db.execute(select(Generation).where(Generation.id == generation_id))
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")
    await db.delete(gen)
    await db.flush()
