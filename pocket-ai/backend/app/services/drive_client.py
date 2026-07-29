"""Google Drive v3 REST client.

Thin and async, over httpx. Handles the three things that actually matter for a
durable archive: finding what we already wrote, resuming an interrupted upload, and
backing off instead of hammering a rate-limited API.

Under the ``drive.file`` scope every search is implicitly scoped to files this app
created — which is exactly the property idempotency needs, and means a query can
never surface the user's unrelated documents.
"""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass

import httpx

from ..core.logging import get_logger
from .google_auth import GoogleOAuthFlow, NotAuthorized

log = get_logger(__name__)

API_BASE = "https://www.googleapis.com/drive/v3"
UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"

# Resumable chunks must be a multiple of 256 KiB. 8 MiB balances request count
# against how much work an interrupted chunk throws away.
CHUNK_SIZE = 8 * 1024 * 1024

# Files above this go through the resumable path; below it, one multipart request.
RESUMABLE_THRESHOLD = 5 * 1024 * 1024

MAX_ATTEMPTS = 5

# 403 is overloaded: quota/rate errors are retryable, permission errors are not.
# Retrying a permission error just delays a message the user needs to see.
_RETRYABLE_403_REASONS = {
    "rateLimitExceeded",
    "userRateLimitExceeded",
    "sharingRateLimitExceeded",
    "quotaExceeded",
}


class DriveError(RuntimeError):
    """A Drive API call failed in a way retrying will not fix."""


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    mime_type: str = ""
    size: int = 0


def escape_query_value(value: str) -> str:
    """Escape a literal for a Drive query string.

    Drive query values are single-quoted, so an apostrophe in a meeting title —
    "Priya's 1:1" — terminates the string early and produces a syntax error or,
    worse, a query that matches the wrong thing.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _retry_after(response: httpx.Response, attempt: int) -> float:
    """Backoff delay, honouring Retry-After when the server sends one."""
    header = response.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    # Full jitter: without it, concurrent uploads retry in lockstep and recreate
    # the burst that triggered the limit.
    return random.uniform(0, min(2**attempt, 32))


def _is_retryable(response: httpx.Response) -> bool:
    if response.status_code == 429 or response.status_code >= 500:
        return True
    if response.status_code != 403:
        return False
    try:
        errors = response.json().get("error", {}).get("errors", [])
    except ValueError:
        return False
    return any(e.get("reason") in _RETRYABLE_403_REASONS for e in errors)


class DriveClient:
    def __init__(
        self,
        oauth: GoogleOAuthFlow,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep=asyncio.sleep,
    ) -> None:
        self.oauth = oauth
        self._transport = transport
        self._sleep = sleep  # injectable so tests exercise backoff without waiting

    def _client(self, timeout: float = 60.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self._transport)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        content: bytes | None = None,
        headers: dict | None = None,
        timeout: float = 60.0,
        expect: tuple[int, ...] = (200, 201),
    ) -> httpx.Response:
        last: httpx.Response | None = None

        for attempt in range(MAX_ATTEMPTS):
            token = await self.oauth.access_token()
            request_headers = {"Authorization": f"Bearer {token}", **(headers or {})}

            async with self._client(timeout) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    content=content,
                    headers=request_headers,
                )

            if response.status_code in expect:
                return response

            # A 401 mid-flight means the token died sooner than its stated expiry.
            # Force one refresh and retry rather than failing the whole export.
            if response.status_code == 401 and attempt == 0:
                log.info("drive.token_rejected_refreshing")
                credentials = self.oauth.store.load()
                if credentials is not None:
                    await self.oauth.refresh(credentials)
                continue

            if not _is_retryable(response) or attempt == MAX_ATTEMPTS - 1:
                raise DriveError(
                    f"{method} {url} failed with {response.status_code}: {response.text[:500]}"
                )

            delay = _retry_after(response, attempt)
            log.warning(
                "drive.retry", status=response.status_code, attempt=attempt + 1, delay=delay
            )
            await self._sleep(delay)
            last = response

        raise DriveError(f"{method} {url} exhausted retries: {last}")

    # -- lookup ----------------------------------------------------------------

    async def find(
        self,
        *,
        name: str | None = None,
        parent: str | None = None,
        mime_type: str | None = None,
        app_properties: dict[str, str] | None = None,
    ) -> DriveFile | None:
        clauses = ["trashed = false"]
        if name:
            clauses.append(f"name = '{escape_query_value(name)}'")
        if parent:
            clauses.append(f"'{escape_query_value(parent)}' in parents")
        if mime_type:
            clauses.append(f"mimeType = '{escape_query_value(mime_type)}'")
        for key, value in (app_properties or {}).items():
            clauses.append(
                f"appProperties has {{ key='{escape_query_value(key)}' "
                f"and value='{escape_query_value(value)}' }}"
            )

        response = await self._request(
            "GET",
            f"{API_BASE}/files",
            params={
                "q": " and ".join(clauses),
                "fields": "files(id,name,mimeType,size)",
                "pageSize": 10,
                "spaces": "drive",
            },
            expect=(200,),
        )
        files = response.json().get("files", [])
        if not files:
            return None
        first = files[0]
        return DriveFile(
            id=first["id"],
            name=first.get("name", ""),
            mime_type=first.get("mimeType", ""),
            size=int(first.get("size", 0) or 0),
        )

    async def ensure_folder(
        self, name: str, *, parent: str | None = None, app_properties: dict | None = None
    ) -> str:
        """Find or create a folder. Idempotent."""
        existing = await self.find(name=name, parent=parent, mime_type=FOLDER_MIME)
        if existing:
            return existing.id

        body: dict = {"name": name, "mimeType": FOLDER_MIME}
        if parent:
            body["parents"] = [parent]
        if app_properties:
            body["appProperties"] = app_properties

        response = await self._request(
            "POST", f"{API_BASE}/files", json_body=body, params={"fields": "id"}
        )
        folder_id = response.json()["id"]
        log.info("drive.folder_created", name=name)
        return folder_id

    # -- upload ----------------------------------------------------------------

    async def upload(
        self,
        *,
        name: str,
        content: bytes,
        parent: str,
        mime_type: str = "application/octet-stream",
        app_properties: dict[str, str] | None = None,
        file_id: str | None = None,
        resumable_session: str | None = None,
    ) -> tuple[str, str | None]:
        """Create or update a file. Returns ``(file_id, live_session_uri)``.

        ``file_id`` updates in place — that is what stops re-export from producing
        ``transcript (2).md``. The returned session URI is non-None only when a
        resumable upload is still in progress, so the caller can persist it and
        resume rather than restart.
        """
        if len(content) >= RESUMABLE_THRESHOLD:
            return await self._upload_resumable(
                name=name,
                content=content,
                parent=parent,
                mime_type=mime_type,
                app_properties=app_properties,
                file_id=file_id,
                session_uri=resumable_session,
            )
        new_id = await self._upload_multipart(
            name=name,
            content=content,
            parent=parent,
            mime_type=mime_type,
            app_properties=app_properties,
            file_id=file_id,
        )
        return new_id, None

    def _metadata(
        self, name: str, parent: str, app_properties: dict | None, *, is_update: bool
    ) -> dict:
        metadata: dict = {"name": name}
        if app_properties:
            metadata["appProperties"] = app_properties
        # `parents` is rejected on update; changing a parent needs addParents instead.
        if not is_update:
            metadata["parents"] = [parent]
        return metadata

    async def _upload_multipart(
        self,
        *,
        name: str,
        content: bytes,
        parent: str,
        mime_type: str,
        app_properties: dict | None,
        file_id: str | None,
    ) -> str:
        metadata = self._metadata(name, parent, app_properties, is_update=bool(file_id))
        boundary = f"----pocketai{random.getrandbits(64):016x}"

        body = b"".join(
            [
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode(),
                json.dumps(metadata).encode("utf-8"),
                f"\r\n--{boundary}\r\nContent-Type: {mime_type}\r\n\r\n".encode(),
                content,
                f"\r\n--{boundary}--\r\n".encode(),
            ]
        )

        url = f"{UPLOAD_BASE}/files" + (f"/{file_id}" if file_id else "")
        response = await self._request(
            "PATCH" if file_id else "POST",
            url,
            params={"uploadType": "multipart", "fields": "id"},
            content=body,
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        )
        return response.json()["id"]

    async def _upload_resumable(
        self,
        *,
        name: str,
        content: bytes,
        parent: str,
        mime_type: str,
        app_properties: dict | None,
        file_id: str | None,
        session_uri: str | None,
    ) -> tuple[str, str | None]:
        total = len(content)
        offset = 0

        if session_uri:
            # Resume: ask how much the server already has rather than assuming.
            offset = await self._session_offset(session_uri, total)
            if offset is None:  # session dead or expired — start over
                session_uri = None
                offset = 0
            elif offset >= total:
                log.info("drive.resumable_already_complete", name=name)
                return file_id or "", None

        if not session_uri:
            session_uri = await self._start_session(
                name=name,
                total=total,
                parent=parent,
                mime_type=mime_type,
                app_properties=app_properties,
                file_id=file_id,
            )
            offset = 0

        while offset < total:
            end = min(offset + CHUNK_SIZE, total)
            chunk = content[offset:end]
            # The session URI is capability-bearing, but Google's own clients still
            # send the bearer token on chunk PUTs and some paths require it.
            headers = {
                "Authorization": f"Bearer {await self.oauth.access_token()}",
                "Content-Range": f"bytes {offset}-{end - 1}/{total}",
                "Content-Type": mime_type,
            }

            async with self._client(timeout=300.0) as client:
                response = await client.put(session_uri, content=chunk, headers=headers)

            if response.status_code in (200, 201):
                log.info("drive.resumable_complete", name=name, bytes=total)
                return response.json()["id"], None

            if response.status_code == 308:
                offset = self._parse_range(response.headers.get("Range"), fallback=end)
                continue

            # Hand the live session URI back so the caller can persist it: the whole
            # point of resumable upload is that a failure here is not a restart.
            raise ResumableInterrupted(
                f"chunk upload failed with {response.status_code}", session_uri, offset
            )

        raise DriveError("resumable upload ended without a completion response")

    async def _start_session(
        self,
        *,
        name: str,
        total: int,
        parent: str,
        mime_type: str,
        app_properties: dict | None,
        file_id: str | None,
    ) -> str:
        metadata = self._metadata(name, parent, app_properties, is_update=bool(file_id))
        url = f"{UPLOAD_BASE}/files" + (f"/{file_id}" if file_id else "")

        response = await self._request(
            "PATCH" if file_id else "POST",
            url,
            params={"uploadType": "resumable"},
            json_body=metadata,
            headers={
                "X-Upload-Content-Type": mime_type,
                "X-Upload-Content-Length": str(total),
            },
            expect=(200, 201),
        )
        location = response.headers.get("Location")
        if not location:
            raise DriveError("resumable session started without a Location header")
        return location

    async def _session_offset(self, session_uri: str, total: int) -> int | None:
        """Bytes the server already holds, or None if the session is gone."""
        async with self._client(timeout=60.0) as client:
            response = await client.put(
                session_uri,
                headers={
                    "Authorization": f"Bearer {await self.oauth.access_token()}",
                    "Content-Range": f"bytes */{total}",
                },
                content=b"",
            )

        if response.status_code in (200, 201):
            return total
        if response.status_code == 308:
            return self._parse_range(response.headers.get("Range"), fallback=0)
        if response.status_code in (404, 410):
            log.info("drive.resumable_session_expired")
            return None
        return None

    @staticmethod
    def _parse_range(header: str | None, *, fallback: int) -> int:
        """`Range: bytes=0-262143` means bytes 0..262143 are stored, so resume at +1."""
        if not header or "-" not in header:
            return fallback
        try:
            return int(header.rsplit("-", 1)[1]) + 1
        except ValueError:
            return fallback

    async def download(self, file_id: str) -> bytes:
        response = await self._request(
            "GET",
            f"{API_BASE}/files/{file_id}",
            params={"alt": "media"},
            expect=(200,),
        )
        return response.content

    async def delete(self, file_id: str) -> None:
        await self._request("DELETE", f"{API_BASE}/files/{file_id}", expect=(200, 204))

    async def about(self) -> dict:
        """Cheap authenticated call, for verifying credentials work."""
        response = await self._request(
            "GET",
            f"{API_BASE}/about",
            params={"fields": "user(emailAddress),storageQuota"},
            expect=(200,),
        )
        return response.json()


class ResumableInterrupted(DriveError):
    """An upload stalled but is resumable. Carries the session URI to persist."""

    def __init__(self, message: str, session_uri: str, offset: int) -> None:
        super().__init__(message)
        self.session_uri = session_uri
        self.offset = offset


__all__ = [
    "CHUNK_SIZE",
    "FOLDER_MIME",
    "RESUMABLE_THRESHOLD",
    "DriveClient",
    "DriveError",
    "DriveFile",
    "NotAuthorized",
    "ResumableInterrupted",
    "escape_query_value",
]
