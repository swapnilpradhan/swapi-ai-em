"""Drive export and OAuth.

The OAuth handlers land in Phase 1. Scope stays ``drive.file`` — files this app
created, nothing else. See docs/capabilities/01-drive-export.md.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.config import Backend, get_settings
from ...models import ExportManifest
from ...services.artifacts import build_artifacts
from ...services.registry import get_registry
from ..store import get_store

router = APIRouter(prefix="/drive", tags=["drive"])

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


class ExportRequest(BaseModel):
    meeting_id: str


@router.post("/export", response_model=ExportManifest)
async def export(request: ExportRequest) -> ExportManifest:
    """Export a meeting's artifacts.

    Idempotent: unchanged artifacts are skipped on their content hash, so re-running
    a full export performs zero writes.
    """
    store = get_store()
    meeting = store.get_meeting(request.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")

    artifacts = build_artifacts(
        meeting, store.get_insights(request.meeting_id), speaker_names=store.speaker_names()
    )
    return await get_registry().storage.export_all(meeting, artifacts)


@router.get("/manifest/{meeting_id}", response_model=ExportManifest)
async def manifest(meeting_id: str) -> ExportManifest:
    """Read export state from the archive itself, not from a database.

    This is the property ADR-0002 claims: losing the database is recoverable.
    """
    result = await get_registry().storage.read_manifest(meeting_id)
    if result is None:
        raise HTTPException(status_code=404, detail="no manifest for that meeting")
    return result


@router.get("/status")
async def status() -> dict:
    settings = get_settings()
    return {
        "backend": settings.storage_backend.value,
        "scope": DRIVE_SCOPE,
        "root_folder": settings.drive_root_folder_name,
        "configured": settings.storage_backend is Backend.REAL,
        "stub_root": str(settings.drive_stub_root),
    }


@router.get("/oauth/start")
async def oauth_start() -> dict:
    raise HTTPException(
        status_code=501,
        detail="Phase 1 — see docs/capabilities/01-drive-export.md",
    )


@router.get("/oauth/callback")
async def oauth_callback(code: str = "", state: str = "") -> dict:
    raise HTTPException(
        status_code=501,
        detail="Phase 1 — see docs/capabilities/01-drive-export.md",
    )
