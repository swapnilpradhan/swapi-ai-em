from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime

# Set before any app import: settings are cached at first access, and the API tests
# exercise the real singleton. Without this, the suite writes stub exports into the
# working tree.
_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="pocket-ai-tests-")
os.environ.setdefault("MEDIA_ROOT", _TEST_MEDIA_ROOT)
os.environ.setdefault("APP_ENV", "test")

import pytest  # noqa: E402

from backend.app.api.store import get_store  # noqa: E402
from backend.app.core.config import Settings
from backend.app.models import AudioQuality
from backend.app.services.ingest import build_meeting

RAW_TRANSCRIPT = """\
[00:00:00] Right, let's start with the Kafka migration timeline.
[00:00:12] I'm worried about capacity. We haven't sized the cluster.
[00:00:30] I'll run the capacity analysis and have numbers by Friday.
[00:00:48] Someone should probably review the retention policy at some point.
[00:01:05] Agreed, let's defer the migration to Q4 then.
"""


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(media_root=tmp_path / "media", app_env="test")


@pytest.fixture
def meeting():
    return build_meeting(
        title="Platform Architecture Review",
        occurred_at=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
        audio_bytes=b"fake-audio-bytes",
        raw_transcript=RAW_TRANSCRIPT,
        duration_seconds=3600,
        quality=AudioQuality(snr_db=20.0, clipping_ratio=0.01),
    )


@pytest.fixture
def bad_audio_meeting():
    return build_meeting(
        title="Noisy Room",
        occurred_at=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        audio_bytes=b"other-audio",
        raw_transcript=RAW_TRANSCRIPT,
        duration_seconds=600,
        quality=AudioQuality(snr_db=3.0, clipping_ratio=0.4),
    )


@pytest.fixture(autouse=True)
def clean_store():
    get_store().clear()
    yield
    get_store().clear()
