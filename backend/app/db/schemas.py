"""
Pydantic response/request schemas for the API layer.
"""
from datetime import datetime
from typing import Optional, List, Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request Schemas ──

class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=512)
    workflow_type: str = Field(default="standard_content_generation")


# ── Response Schemas ──

class GenerationStepOut(BaseModel):
    id: UUID
    step_number: int
    agent_id: str
    task_type: str
    status: str
    result_summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    model_config = {"from_attributes": True}


class GenerationOut(BaseModel):
    id: UUID
    topic: str
    workflow_type: str
    status: str
    file_path: Optional[str] = None
    total_duration_ms: Optional[float] = None
    error: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata_")
    created_at: datetime
    updated_at: datetime
    steps: List[GenerationStepOut] = []

    model_config = {"from_attributes": True, "populate_by_name": True}


class GenerationListOut(BaseModel):
    id: UUID
    topic: str
    workflow_type: str
    status: str
    total_duration_ms: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: UUID
    event_type: str
    agent_id: Optional[str] = None
    correlation_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class A2AMessageOut(BaseModel):
    id: UUID
    message_id: str
    sender: str
    receiver: str
    message_type: str
    priority: Optional[int] = None
    content: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    response_time_ms: Optional[float] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
