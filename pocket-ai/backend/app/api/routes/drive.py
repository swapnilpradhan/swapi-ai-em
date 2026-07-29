"""Drive export and OAuth.

Scope is ``drive.file`` — files this app created, nothing else. See
docs/capabilities/01-drive-export.md.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from ...core.config import Backend, get_settings
from ...core.logging import get_logger
from ...models import ExportManifest
from ...services.artifacts import build_artifacts
from ...services.drive_client import DriveError
from ...services.google_auth import SCOPE, NotAuthorized, OAuthError
from ...services.registry import get_registry
from ..store import get_store

router = APIRouter(prefix="/drive", tags=["drive"])
log = get_logger(__name__)


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
    try:
        return await get_registry().storage.export_all(meeting, artifacts)
    except NotAuthorized as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except DriveError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/manifest/{meeting_id}", response_model=ExportManifest)
async def manifest(meeting_id: str) -> ExportManifest:
    """Read export state from the archive itself, not from a database.

    This is the property ADR-0002 claims: losing the database is recoverable.
    """
    try:
        result = await get_registry().storage.read_manifest(meeting_id)
    except NotAuthorized as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="no manifest for that meeting")
    return result


@router.get("/status")
async def status() -> dict:
    settings = get_settings()
    registry = get_registry()
    configured = settings.storage_backend is Backend.REAL

    body: dict = {
        "backend": settings.storage_backend.value,
        "scope": SCOPE,
        "root_folder": settings.drive_root_folder_name,
        "configured": configured,
        "authorized": registry.google_oauth.is_authorized,
        "token_path": str(settings.google_token_path),
        "stub_root": str(settings.drive_stub_root),
    }
    if configured and registry.google_oauth.is_authorized:
        # Round-trips to Drive, so only when there is something to check.
        body["check"] = await registry.storage.check()
    return body


# -- OAuth ---------------------------------------------------------------------


@router.get("/oauth/start")
async def oauth_start(redirect: bool = True):
    """Begin the consent flow.

    Returns a redirect by default so a browser can follow it straight through;
    ``?redirect=false`` returns the URL as JSON for scripted use.
    """
    registry = get_registry()
    try:
        url, state = registry.google_oauth.authorization_url()
    except NotAuthorized as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if redirect:
        return RedirectResponse(url, status_code=307)
    return {"authorization_url": url, "state": state, "scope": SCOPE}


@router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(
    code: str | None = None, state: str | None = None, error: str | None = None
) -> HTMLResponse:
    """Handle Google's redirect back.

    ``state`` is verified inside ``exchange_code``. Without that check an attacker
    could hand the user a callback URL carrying *their* authorization code, silently
    pointing the user's exports at an attacker-controlled Drive.
    """
    if error:
        return _page("Authorization declined", f"Google returned: {error}", ok=False)
    if not code or not state:
        return _page("Missing parameters", "No authorization code in the callback.", ok=False)

    try:
        await get_registry().google_oauth.exchange_code(code, state)
    except OAuthError as exc:
        log.warning("drive.oauth_exchange_failed", error=str(exc))
        return _page("Authorization failed", str(exc), ok=False)

    return _page(
        "Connected to Google Drive",
        "Pocket.ai Studio can now write to its own folder. You can close this tab.",
        ok=True,
    )


@router.post("/oauth/revoke")
async def oauth_revoke() -> dict:
    """Revoke at Google, then drop the local token."""
    await get_registry().google_oauth.revoke()
    return {"status": "revoked"}


def _page(title: str, message: str, *, ok: bool) -> HTMLResponse:
    colour = "#16a34a" if ok else "#dc2626"
    return HTMLResponse(
        f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:system-ui,sans-serif;max-width:34rem;margin:4rem auto;padding:0 1rem">
  <h1 style="color:{colour};font-size:1.25rem">{title}</h1>
  <p style="color:#444;line-height:1.6">{message}</p>
</body></html>""",
        status_code=200 if ok else 400,
    )
