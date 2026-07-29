"""Webhook signature verification and payload extraction.

⚠️  The exact signature scheme is UNVERIFIED — docs.heypocketai.com blocks automated
    fetching, so this implements the common convention (HMAC-SHA256 over the raw body,
    optionally prefixed with a timestamp). If Pocket differs, ``verify_signature`` is
    the only thing that should need changing.

    Until it is confirmed against a real delivery, treat a working signature check as
    unproven. It is wired to fail closed, so a mismatch rejects rather than admits.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from ..core.logging import get_logger

log = get_logger(__name__)


class WebhookRejected(Exception):
    """Delivery failed verification. Never process the payload after this."""


def _candidate_digests(secret: str, body: bytes, timestamp: str | None) -> set[str]:
    """Digests for the plausible signing conventions.

    Providers differ on whether the timestamp is part of the signed payload. Computing
    both and accepting either keeps us working across that difference without weakening
    anything: each candidate still requires the shared secret.
    """
    key = secret.encode("utf-8")
    candidates = {hmac.new(key, body, hashlib.sha256).hexdigest()}
    if timestamp:
        signed = f"{timestamp}.".encode() + body
        candidates.add(hmac.new(key, signed, hashlib.sha256).hexdigest())
    return candidates


def _normalize(signature: str) -> str:
    """Strip a ``sha256=`` / ``v1=`` scheme prefix if present."""
    value = signature.strip()
    for prefix in ("sha256=", "v1=", "hmac-sha256="):
        if value.lower().startswith(prefix):
            return value[len(prefix) :]
    return value


def verify_signature(
    *,
    secret: str,
    body: bytes,
    signature: str | None,
    timestamp: str | None = None,
    tolerance_seconds: int = 300,
) -> None:
    """Raise ``WebhookRejected`` unless the delivery is authentic and fresh.

    Fails closed on a missing secret. An unauthenticated webhook endpoint that ingests
    whatever it is handed is a way for anyone who learns the URL to inject meetings
    into a personal archive.
    """
    if not secret:
        raise WebhookRejected(
            "POCKET_WEBHOOK_SECRET is not set; refusing to accept unverified deliveries"
        )
    if not signature:
        raise WebhookRejected("missing signature header")

    if timestamp:
        try:
            age = abs(time.time() - float(timestamp))
        except ValueError:
            raise WebhookRejected("malformed timestamp header") from None
        if age > tolerance_seconds:
            # Without this, a captured delivery stays replayable forever.
            raise WebhookRejected(f"stale delivery ({age:.0f}s old)")

    provided = _normalize(signature)
    expected = _candidate_digests(secret, body, timestamp)

    # compare_digest on every candidate: constant-time, no early exit on first char.
    if not any(hmac.compare_digest(provided, candidate) for candidate in expected):
        raise WebhookRejected("signature mismatch")


# --- payload extraction ------------------------------------------------------

# Events that mean "this recording has new content worth pulling". Unverified against
# the real taxonomy, which is why extraction below is tolerant rather than exhaustive.
KNOWN_EVENTS = frozenset(
    {
        "recording.completed",
        "recording.updated",
        "transcript.completed",
        "transcript.updated",
        "summary.completed",
        "action_items.completed",
        "translation.completed",
    }
)

_ID_KEYS = ("recordingId", "recording_id", "id")


def extract_recording_id(payload: dict[str, Any]) -> str | None:
    """Find the recording id wherever the payload happens to put it.

    Deliberately structural rather than schema-bound: we only need the id, and being
    tolerant here means a naming difference costs nothing. The authoritative content
    is fetched from the API afterwards, so a malformed payload cannot inject data.
    """
    for key in _ID_KEYS:
        value = payload.get(key)
        if isinstance(value, str | int) and str(value):
            return str(value)

    for container in ("recording", "data", "object", "payload"):
        nested = payload.get(container)
        if isinstance(nested, dict):
            found = extract_recording_id(nested)
            if found:
                return found

    return None


def extract_event(payload: dict[str, Any]) -> str:
    for key in ("event", "type", "eventType", "event_type"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"
