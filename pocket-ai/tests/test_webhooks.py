"""Webhook verification and payload extraction.

The negative cases matter most here. An unauthenticated webhook endpoint that ingests
whatever it is handed lets anyone who learns the URL inject meetings into a personal
archive, so every one of these rejections is load-bearing.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from backend.app.services.webhooks import (
    WebhookRejected,
    extract_event,
    extract_recording_id,
    verify_signature,
)

SECRET = "whsec_test_secret"
BODY = b'{"event":"recording.completed","recordingId":"rec_123"}'


def sign(body: bytes, secret: str = SECRET, timestamp: str | None = None) -> str:
    payload = f"{timestamp}.".encode() + body if timestamp else body
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestSignatureVerification:
    def test_valid_signature_passes(self):
        verify_signature(secret=SECRET, body=BODY, signature=sign(BODY))

    def test_scheme_prefix_is_tolerated(self):
        verify_signature(secret=SECRET, body=BODY, signature=f"sha256={sign(BODY)}")

    def test_timestamped_scheme_passes(self):
        now = str(int(time.time()))
        verify_signature(
            secret=SECRET, body=BODY, signature=sign(BODY, timestamp=now), timestamp=now
        )

    def test_wrong_secret_is_rejected(self):
        with pytest.raises(WebhookRejected, match="mismatch"):
            verify_signature(secret=SECRET, body=BODY, signature=sign(BODY, "other-secret"))

    def test_tampered_body_is_rejected(self):
        signature = sign(BODY)
        with pytest.raises(WebhookRejected, match="mismatch"):
            verify_signature(secret=SECRET, body=BODY + b" ", signature=signature)

    def test_missing_signature_is_rejected(self):
        with pytest.raises(WebhookRejected, match="missing signature"):
            verify_signature(secret=SECRET, body=BODY, signature=None)

    def test_missing_secret_fails_closed(self):
        """No secret configured must mean 'reject everything', not 'accept everything'."""
        with pytest.raises(WebhookRejected, match="not set"):
            verify_signature(secret="", body=BODY, signature=sign(BODY))

    def test_stale_delivery_is_rejected(self):
        """Without a freshness window a captured delivery stays replayable forever."""
        old = str(int(time.time()) - 3600)
        with pytest.raises(WebhookRejected, match="stale"):
            verify_signature(
                secret=SECRET,
                body=BODY,
                signature=sign(BODY, timestamp=old),
                timestamp=old,
                tolerance_seconds=300,
            )

    def test_fresh_delivery_within_tolerance_passes(self):
        recent = str(int(time.time()) - 10)
        verify_signature(
            secret=SECRET,
            body=BODY,
            signature=sign(BODY, timestamp=recent),
            timestamp=recent,
            tolerance_seconds=300,
        )

    def test_malformed_timestamp_is_rejected(self):
        with pytest.raises(WebhookRejected, match="malformed"):
            verify_signature(
                secret=SECRET, body=BODY, signature=sign(BODY), timestamp="not-a-number"
            )


class TestPayloadExtraction:
    def test_top_level_id(self):
        assert extract_recording_id({"recordingId": "rec_1"}) == "rec_1"

    def test_snake_case_id(self):
        assert extract_recording_id({"recording_id": "rec_2"}) == "rec_2"

    def test_nested_under_data(self):
        assert extract_recording_id({"data": {"recordingId": "rec_3"}}) == "rec_3"

    def test_nested_under_recording(self):
        assert extract_recording_id({"recording": {"id": "rec_4"}}) == "rec_4"

    def test_numeric_id_is_stringified(self):
        assert extract_recording_id({"id": 99}) == "99"

    def test_absent_id_returns_none(self):
        assert extract_recording_id({"event": "ping"}) is None

    def test_event_extraction_variants(self):
        assert extract_event({"event": "recording.completed"}) == "recording.completed"
        assert extract_event({"type": "summary.completed"}) == "summary.completed"
        assert extract_event({}) == "unknown"
