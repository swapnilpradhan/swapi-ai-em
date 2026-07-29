"""Inbound webhooks.

The handler verifies, extracts a recording id, acknowledges, and does the real work
in the background. Returning fast matters: providers time out and retry, and a slow
handler turns one recording into several redeliveries.

Nothing from the payload is trusted beyond the id — the content is always re-fetched
from the API. That keeps a forged or malformed body from injecting anything.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Request, Response

from ...core.config import get_settings
from ...core.logging import get_logger
from ...services.registry import get_registry
from ...services.sync import ingest_recording
from ...services.webhooks import (
    KNOWN_EVENTS,
    WebhookRejected,
    extract_event,
    extract_recording_id,
    verify_signature,
)
from ..store import get_store

router = APIRouter(prefix="/hooks", tags=["hooks"])
log = get_logger(__name__)


async def _pull(recording_id: str) -> None:
    await ingest_recording(recording_id, get_registry(), get_store())


@router.post("/pocket")
async def pocket_webhook(request: Request, background: BackgroundTasks) -> Response:
    """Receive a Pocket webhook and pull the named recording.

    Always 2xx once verified, including for events we ignore. A non-2xx tells the
    provider to retry, and retrying something we deliberately skipped just generates
    noise until the delivery is abandoned.
    """
    settings = get_settings()
    body = await request.body()

    try:
        verify_signature(
            secret=settings.pocket_webhook_secret,
            body=body,
            signature=request.headers.get(settings.pocket_webhook_signature_header),
            timestamp=request.headers.get(settings.pocket_webhook_timestamp_header),
            tolerance_seconds=settings.pocket_webhook_tolerance_seconds,
        )
    except WebhookRejected as exc:
        log.warning("webhook.rejected", reason=str(exc))
        # 401 rather than 400: this is an authentication failure, and the provider
        # should surface it rather than treat it as a transient error worth retrying.
        return Response(status_code=401, content=json.dumps({"error": str(exc)}))

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400, content=json.dumps({"error": "invalid JSON"}))
    if not isinstance(payload, dict):
        return Response(status_code=400, content=json.dumps({"error": "expected an object"}))

    event = extract_event(payload)
    recording_id = extract_recording_id(payload)

    if recording_id is None:
        log.warning("webhook.no_recording_id", event=event)
        return Response(status_code=202, content=json.dumps({"status": "ignored", "event": event}))

    # Unknown events still trigger a pull. The event taxonomy is unverified, and the
    # pull is idempotent — being wrong costs one redundant fetch, whereas ignoring a
    # real event silently loses a recording.
    known = event in KNOWN_EVENTS
    if not known:
        log.info("webhook.unknown_event", event=event)

    background.add_task(_pull, recording_id)

    return Response(
        status_code=202,
        media_type="application/json",
        content=json.dumps(
            {"status": "accepted", "event": event, "recording_id": recording_id, "known": known}
        ),
    )


@router.get("/pocket/status")
async def webhook_status() -> dict:
    settings = get_settings()
    return {
        "configured": settings.webhook_configured,
        "signature_header": settings.pocket_webhook_signature_header,
        "timestamp_header": settings.pocket_webhook_timestamp_header,
        "tolerance_seconds": settings.pocket_webhook_tolerance_seconds,
        "known_events": sorted(KNOWN_EVENTS),
        "note": (
            "Signature scheme and event names are unverified against Pocket's spec — "
            "see docs/capabilities/00-pocket-ingest.md"
        ),
    }
