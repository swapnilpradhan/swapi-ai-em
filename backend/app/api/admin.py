"""
Admin API routes for audit logs, A2A messages, agent metrics, and system overview.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import AuditLog, A2AMessageRecord
from app.db.schemas import AuditLogOut, A2AMessageOut, PaginatedResponse

logger = logging.getLogger("api.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit-logs", response_model=PaginatedResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Paginated, filterable audit log."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if event_type:
        query = query.where(AuditLog.event_type == event_type)
        count_query = count_query.where(AuditLog.event_type == event_type)
    if agent_id:
        query = query.where(AuditLog.agent_id == agent_id)
        count_query = count_query.where(AuditLog.agent_id == agent_id)
    if correlation_id:
        query = query.where(AuditLog.correlation_id == correlation_id)
        count_query = count_query.where(AuditLog.correlation_id == correlation_id)

    total = (await db.execute(count_query)).scalar() or 0
    pages = max(1, (total + page_size - 1) // page_size)

    query = query.order_by(desc(AuditLog.timestamp)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/messages", response_model=PaginatedResponse)
async def list_a2a_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sender: Optional[str] = None,
    receiver: Optional[str] = None,
    message_type: Optional[str] = None,
    correlation_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Paginated, filterable A2A message history."""
    query = select(A2AMessageRecord)
    count_query = select(func.count(A2AMessageRecord.id))

    if sender:
        query = query.where(A2AMessageRecord.sender == sender)
        count_query = count_query.where(A2AMessageRecord.sender == sender)
    if receiver:
        query = query.where(A2AMessageRecord.receiver == receiver)
        count_query = count_query.where(A2AMessageRecord.receiver == receiver)
    if message_type:
        query = query.where(A2AMessageRecord.message_type == message_type)
        count_query = count_query.where(A2AMessageRecord.message_type == message_type)
    if correlation_id:
        query = query.where(A2AMessageRecord.correlation_id == correlation_id)
        count_query = count_query.where(A2AMessageRecord.correlation_id == correlation_id)

    total = (await db.execute(count_query)).scalar() or 0
    pages = max(1, (total + page_size - 1) // page_size)

    query = query.order_by(desc(A2AMessageRecord.timestamp)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[A2AMessageOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/metrics")
async def get_admin_metrics(db: AsyncSession = Depends(get_db)):
    """Dashboard KPI metrics pulled from the database."""
    from app.db.models import Generation, GenerationStep

    total_gens = (await db.execute(select(func.count(Generation.id)))).scalar() or 0
    completed = (await db.execute(
        select(func.count(Generation.id)).where(Generation.status == "completed")
    )).scalar() or 0
    failed = (await db.execute(
        select(func.count(Generation.id)).where(Generation.status == "failed")
    )).scalar() or 0
    avg_duration = (await db.execute(
        select(func.avg(Generation.total_duration_ms)).where(Generation.status == "completed")
    )).scalar()

    total_messages = (await db.execute(select(func.count(A2AMessageRecord.id)))).scalar() or 0
    total_audit_events = (await db.execute(select(func.count(AuditLog.id)))).scalar() or 0

    # Per-agent step stats
    agent_stats_q = (
        select(
            GenerationStep.agent_id,
            func.count(GenerationStep.id).label("total"),
            func.count(GenerationStep.id).filter(GenerationStep.status == "completed").label("completed"),
            func.avg(GenerationStep.duration_ms).label("avg_duration_ms"),
        )
        .group_by(GenerationStep.agent_id)
    )
    agent_rows = (await db.execute(agent_stats_q)).all()
    agent_stats = {
        row.agent_id: {
            "total_steps": row.total,
            "completed_steps": row.completed,
            "avg_duration_ms": round(row.avg_duration_ms, 1) if row.avg_duration_ms else None,
        }
        for row in agent_rows
    }

    return {
        "total_generations": total_gens,
        "completed_generations": completed,
        "failed_generations": failed,
        "success_rate": round(completed / total_gens * 100, 1) if total_gens else 0,
        "avg_duration_ms": round(avg_duration, 1) if avg_duration else None,
        "total_a2a_messages": total_messages,
        "total_audit_events": total_audit_events,
        "agent_stats": agent_stats,
    }


@router.get("/agents")
async def get_agents_overview():
    """Agent status from the in-memory monitoring service."""
    from app.services.monitoring_service import monitoring_service
    from app.core.observability import observability_service

    agent_ids = ["topic_breakdown_agent", "research_agent", "html_generation_agent"]
    agents_out = {}
    for aid in agent_ids:
        metrics = observability_service.agent_metrics.get(aid)
        agents_out[aid] = {
            "status": "active" if metrics else "unknown",
            "tasks_completed": metrics.tasks_completed if metrics else 0,
            "tasks_failed": metrics.tasks_failed if metrics else 0,
            "avg_task_duration": metrics.average_task_duration if metrics else 0,
            "tokens_used": metrics.tokens_used if metrics else 0,
            "error_rate": metrics.error_rate if metrics else 0,
        }
    return agents_out
