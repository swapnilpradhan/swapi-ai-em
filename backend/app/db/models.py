"""
SQLAlchemy ORM models for the Multi-Agent EM Platform.

Tables:
  - generations        — one row per HTML generation request
  - generation_steps   — one row per agent step within a generation
  - audit_logs         — significant system events
  - a2a_messages       — every inter-agent message
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Generation(Base):
    """A single content-generation run."""
    __tablename__ = "generations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(String(512), nullable=False, index=True)
    workflow_type = Column(String(128), nullable=False, default="standard_content_generation")
    status = Column(String(32), nullable=False, default="pending")  # pending, running, completed, failed
    html_content = Column(Text, nullable=True)
    file_path = Column(String(1024), nullable=True)
    total_duration_ms = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    steps = relationship("GenerationStep", back_populates="generation", order_by="GenerationStep.step_number", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_generations_status", "status"),
        Index("ix_generations_created", "created_at"),
    )


class GenerationStep(Base):
    """One agent step within a generation workflow."""
    __tablename__ = "generation_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(UUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    agent_id = Column(String(128), nullable=False)
    task_type = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="pending")  # pending, running, completed, failed
    result_summary = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Float, nullable=True)

    generation = relationship("Generation", back_populates="steps")

    __table_args__ = (
        Index("ix_genstep_gen_step", "generation_id", "step_number"),
    )


class AuditLog(Base):
    """Significant system events for full auditability."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(128), nullable=False, index=True)  # generation_started, step_completed, error, cache_hit, etc.
    agent_id = Column(String(128), nullable=True, index=True)
    correlation_id = Column(String(256), nullable=True, index=True)
    payload = Column(JSONB, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)


class A2AMessageRecord(Base):
    """Persisted copy of every inter-agent message."""
    __tablename__ = "a2a_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(String(256), nullable=False, unique=True)
    sender = Column(String(128), nullable=False, index=True)
    receiver = Column(String(128), nullable=False, index=True)
    message_type = Column(String(64), nullable=False, index=True)
    priority = Column(Integer, nullable=True)
    content = Column(JSONB, nullable=True)
    correlation_id = Column(String(256), nullable=True, index=True)
    response_time_ms = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
