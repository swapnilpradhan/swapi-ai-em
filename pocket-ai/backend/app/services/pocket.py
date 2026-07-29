"""Pocket API client.

Ingest is webhook-driven pull: a hook tells us *what* changed, and we fetch the
authoritative copy through here. See docs/adr/0008-webhook-driven-ingest.md.

⚠️  ENDPOINT PATHS AND FIELD NAMES ARE UNVERIFIED. They were derived from public
    documentation summaries, not from the spec itself (docs.heypocketai.com blocks
    automated fetching). Everything provider-specific is centralized in ``PocketRoutes``
    and ``_parse_*`` below so correcting them is a small, contained edit. Confirm
    against a real API key before trusting this in production — see
    docs/capabilities/00-pocket-ingest.md for the verification checklist.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..core.config import Settings
from ..core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class PocketRoutes:
    """Every provider-specific path in one place.

    Unverified — if the real API differs, this is the only thing that should need
    changing, plus the field mapping in ``_parse_recording``.
    """

    list_recordings: str = "/v1/recordings"
    recording_detail: str = "/v1/recordings/{recording_id}"
    transcript: str = "/v1/recordings/{recording_id}/transcript"


ROUTES = PocketRoutes()


@dataclass(frozen=True)
class PocketSegment:
    """One transcript segment as Pocket returns it: ``{text, start, end, speaker?}``.

    ``start``/``end`` are seconds (float) upstream; we normalize to integer
    milliseconds at the boundary so nothing downstream has to care.
    """

    text: str
    start_ms: int
    end_ms: int
    speaker: str | None = None


@dataclass(frozen=True)
class PocketRecording:
    """A recording plus its transcript, normalized into our vocabulary."""

    recording_id: str
    title: str
    occurred_at: datetime
    duration_seconds: float
    segments: list[PocketSegment]
    audio_url: str | None = None
    summary: str | None = None
    tags: list[str] = field(default_factory=list)
    updated_at: datetime | None = None

    @property
    def has_speaker_labels(self) -> bool:
        return any(s.speaker for s in self.segments)


class PocketAuthError(RuntimeError):
    """Bad or missing API key. Not retryable — surfacing it beats silent retries."""


class PocketNotFound(RuntimeError):
    """The recording is gone, or the key cannot see it."""


# --- parsing -----------------------------------------------------------------
# Tolerant by design: the exact field names are unverified, so accept the plausible
# spellings rather than KeyError-ing on a naming difference. A wrong guess should
# degrade to a missing optional field, not a failed ingest.


def _first(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _to_ms(value: Any) -> int:
    """Seconds (the documented unit) to milliseconds."""
    if value is None:
        return 0
    try:
        return int(round(float(value) * 1000))
    except (TypeError, ValueError):
        return 0


def parse_segments(raw: Any) -> list[PocketSegment]:
    if isinstance(raw, dict):
        raw = _first(raw, "segments", "transcript", "items", default=[])
    if not isinstance(raw, list):
        return []

    segments: list[PocketSegment] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(_first(item, "text", "content", default="")).strip()
        if not text:
            continue
        start_ms = _to_ms(_first(item, "start", "start_time", "startTime"))
        end_ms = _to_ms(_first(item, "end", "end_time", "endTime"))
        speaker = _first(item, "speaker", "speaker_label", "speakerLabel")
        segments.append(
            PocketSegment(
                text=text,
                start_ms=start_ms,
                end_ms=max(end_ms, start_ms),
                speaker=str(speaker) if speaker else None,
            )
        )
    return segments


def parse_recording(payload: dict[str, Any], segments_payload: Any = None) -> PocketRecording:
    recording_id = str(_first(payload, "recordingId", "recording_id", "id", default=""))
    if not recording_id:
        raise ValueError("recording payload has no id")

    segments = parse_segments(segments_payload if segments_payload is not None else payload)
    occurred = _to_datetime(
        _first(payload, "recordingDate", "recorded_at", "createdAt", "created_at", "date")
    ) or datetime.now(UTC)

    duration = _first(payload, "duration", "durationSeconds", "duration_seconds")
    if duration is None:
        # Fall back to the transcript's own span rather than reporting zero.
        duration = (segments[-1].end_ms / 1000) if segments else 0.0

    tags = _first(payload, "recordingTags", "tags", default=[]) or []

    return PocketRecording(
        recording_id=recording_id,
        title=str(_first(payload, "recordingTitle", "title", "name", default="Untitled")),
        occurred_at=occurred,
        duration_seconds=float(duration),
        segments=segments,
        audio_url=_first(payload, "audioUrl", "audio_url"),
        summary=_first(payload, "summary"),
        tags=[str(t) for t in tags if t],
        updated_at=_to_datetime(_first(payload, "updatedAt", "updated_at")),
    )


# --- implementations ---------------------------------------------------------


class StubPocketClient:
    """Offline client returning deterministic recordings.

    Deliberately produces speaker labels, because that is the upstream behaviour that
    matters most to the pipeline — it exercises the "skip diarization" path that the
    real API is expected to trigger.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fetched: list[str] = []

    def _make(self, recording_id: str) -> PocketRecording:
        return PocketRecording(
            recording_id=recording_id,
            title=f"[stub] Recording {recording_id}",
            occurred_at=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
            duration_seconds=180.0,
            segments=[
                PocketSegment(
                    text="Let's talk about the migration timeline.",
                    start_ms=0,
                    end_ms=8000,
                    speaker="Speaker 1",
                ),
                PocketSegment(
                    text="I'll run the capacity analysis and have numbers by Friday.",
                    start_ms=8000,
                    end_ms=17000,
                    speaker="Speaker 2",
                ),
                PocketSegment(
                    text="Someone should probably look at the retention policy.",
                    start_ms=17000,
                    end_ms=24000,
                    speaker="Speaker 1",
                ),
            ],
            audio_url=None,
            tags=["stub"],
            updated_at=datetime(2026, 7, 29, 10, 5, tzinfo=UTC),
        )

    async def get_recording(self, recording_id: str) -> PocketRecording:
        self.fetched.append(recording_id)
        return self._make(recording_id)

    async def list_recordings(
        self, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[PocketRecording], str | None]:
        if cursor:  # single synthetic page keeps backfill tests terminating
            return [], None
        return [self._make(f"stub-{i}") for i in range(min(limit, 3))], None

    async def download_audio(self, recording: PocketRecording) -> bytes | None:
        return None


class HttpPocketClient:
    """Real client. Bearer auth with a ``pk_...`` API key.

    Retries on 429 and 5xx with exponential backoff; auth and 404 fail immediately,
    because retrying those just delays a message the user needs to see.
    """

    MAX_ATTEMPTS = 4

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.pocket_api_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.pocket_api_key}",
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        import httpx

        url = f"{self.base_url}{path}"
        delay = 1.0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(1, self.MAX_ATTEMPTS + 1):
                response = await client.get(url, headers=self._headers(), params=params)

                if response.status_code in (401, 403):
                    raise PocketAuthError(
                        f"Pocket API rejected the key ({response.status_code}). "
                        "Check POCKET_API_KEY."
                    )
                if response.status_code == 404:
                    raise PocketNotFound(f"not found: {path}")
                if response.status_code < 400:
                    return response.json()

                retryable = response.status_code == 429 or response.status_code >= 500
                if not retryable or attempt == self.MAX_ATTEMPTS:
                    response.raise_for_status()

                # Honour Retry-After when the server sends it; it knows better than we do.
                wait = float(response.headers.get("Retry-After") or delay)
                log.warning("pocket.retry", path=path, status=response.status_code, wait=wait)
                await asyncio.sleep(wait)
                delay *= 2

        raise RuntimeError("unreachable")

    async def get_recording(self, recording_id: str) -> PocketRecording:
        detail = await self._get(ROUTES.recording_detail.format(recording_id=recording_id))
        if isinstance(detail, dict):
            detail = detail.get("recording", detail)

        # Transcript may be embedded in the detail response or need a second call.
        segments_payload: Any = detail
        if not parse_segments(detail):
            try:
                segments_payload = await self._get(
                    ROUTES.transcript.format(recording_id=recording_id)
                )
            except PocketNotFound:
                # A recording that has not finished processing has no transcript yet.
                segments_payload = []

        return parse_recording(detail, segments_payload)

    async def list_recordings(
        self, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[PocketRecording], str | None]:
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        payload = await self._get(ROUTES.list_recordings, params)
        items = (
            payload
            if isinstance(payload, list)
            else _first(payload, "recordings", "items", "data", default=[])
        )
        next_cursor = (
            None
            if isinstance(payload, list)
            else _first(payload, "nextCursor", "next_cursor", "cursor")
        )

        recordings = []
        for item in items or []:
            try:
                recordings.append(parse_recording(item))
            except ValueError:
                log.warning("pocket.skip_unparseable_recording")
        return recordings, next_cursor

    async def download_audio(self, recording: PocketRecording) -> bytes | None:
        if not recording.audio_url:
            return None

        import httpx

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            # audioUrl is often a pre-signed URL; send auth only for same-host URLs
            # so the key is never leaked to a third-party storage host.
            same_host = recording.audio_url.startswith(self.base_url)
            response = await client.get(
                recording.audio_url, headers=self._headers() if same_host else None
            )
            if response.status_code >= 400:
                log.warning("pocket.audio_download_failed", status=response.status_code)
                return None
            return response.content
