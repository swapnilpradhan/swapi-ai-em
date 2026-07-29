"""An in-memory Google Drive, served through ``httpx.MockTransport``.

Good enough to exercise the real client end to end — query parsing, multipart and
resumable uploads, 308 continuation, backoff, token refresh — without a network or a
credential. The point is that the code under test is the production code path, not a
mock of it.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field

import httpx

FOLDER_MIME = "application/vnd.google-apps.folder"


@dataclass
class FakeFile:
    id: str
    name: str
    mime_type: str
    parents: list[str] = field(default_factory=list)
    app_properties: dict[str, str] = field(default_factory=dict)
    content: bytes = b""
    trashed: bool = False


@dataclass
class ResumableSession:
    upload_id: str
    file_id: str | None
    name: str
    parent: str
    mime_type: str
    app_properties: dict
    total: int
    received: bytearray = field(default_factory=bytearray)


class FakeDrive:
    """Tracks state and counts calls so tests can assert on request volume."""

    def __init__(self) -> None:
        self.files: dict[str, FakeFile] = {}
        self.sessions: dict[str, ResumableSession] = {}
        self.calls: list[tuple[str, str]] = []
        self.uploads = 0
        self.token_refreshes = 0
        # Queue of (status, body) to serve before behaving normally — lets a test
        # drive the retry path deterministically.
        self.failures: list[tuple[int, dict]] = []
        self.access_token = "access-1"
        self.fail_chunk_after: int | None = None
        self._chunks_served = 0

    # -- helpers ---------------------------------------------------------------

    def add_folder(self, name: str, parent: str | None = None, **props) -> str:
        file_id = f"folder-{uuid.uuid4().hex[:8]}"
        self.files[file_id] = FakeFile(
            id=file_id,
            name=name,
            mime_type=FOLDER_MIME,
            parents=[parent] if parent else [],
            app_properties=props,
        )
        return file_id

    def by_name(self, name: str) -> FakeFile | None:
        return next((f for f in self.files.values() if f.name == name and not f.trashed), None)

    def children(self, parent_id: str) -> list[FakeFile]:
        return [f for f in self.files.values() if parent_id in f.parents and not f.trashed]

    # -- query -----------------------------------------------------------------

    def _matches(self, file: FakeFile, query: str) -> bool:
        if file.trashed:
            return False

        if (name := re.search(r"name = '((?:[^'\\]|\\.)*)'", query)) is not None:
            wanted = name.group(1).replace("\\'", "'").replace("\\\\", "\\")
            if file.name != wanted:
                return False

        if (parent := re.search(r"'((?:[^'\\]|\\.)*)' in parents", query)) is not None:
            if parent.group(1) not in file.parents:
                return False

        if (mime := re.search(r"mimeType = '([^']*)'", query)) is not None:
            if file.mime_type != mime.group(1):
                return False

        for key, value in re.findall(
            r"appProperties has \{ key='([^']*)' and value='((?:[^'\\]|\\.)*)' \}", query
        ):
            if file.app_properties.get(key) != value.replace("\\'", "'"):
                return False

        return True

    # -- transport -------------------------------------------------------------

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))

        # Queued failures come first so a test can script the token endpoint too.
        if self.failures:
            status, body = self.failures.pop(0)
            return httpx.Response(status, json=body)
        if path == "/token":
            return self._token(request)
        if request.headers.get("Authorization") != f"Bearer {self.access_token}":
            return httpx.Response(401, json={"error": {"message": "invalid credentials"}})

        if path.startswith("/upload/drive/v3/files"):
            return self._upload(request)
        if path.startswith("/resumable/"):
            return self._resumable_chunk(request)
        if path == "/drive/v3/files":
            return self._list_or_create(request)
        if path.startswith("/drive/v3/files/"):
            return self._file(request)
        if path == "/drive/v3/about":
            return httpx.Response(
                200, json={"user": {"emailAddress": "user@example.test"}, "storageQuota": {}}
            )

        return httpx.Response(404, json={"error": {"message": f"no route {path}"}})

    def _token(self, request: httpx.Request) -> httpx.Response:
        body = dict(httpx.QueryParams(request.content.decode()))
        if body.get("grant_type") == "refresh_token":
            self.token_refreshes += 1
            self.access_token = f"access-{self.token_refreshes + 1}"
            # Google normally omits refresh_token on refresh — model that, because
            # the client must not clobber the stored one.
            return httpx.Response(200, json={"access_token": self.access_token, "expires_in": 3600})
        return httpx.Response(
            200,
            json={
                "access_token": self.access_token,
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/drive.file",
            },
        )

    def _list_or_create(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            query = request.url.params.get("q", "")
            matched = [f for f in self.files.values() if self._matches(f, query)]
            return httpx.Response(
                200,
                json={
                    "files": [
                        {
                            "id": f.id,
                            "name": f.name,
                            "mimeType": f.mime_type,
                            "size": str(len(f.content)),
                        }
                        for f in matched
                    ]
                },
            )

        body = json.loads(request.content)
        file_id = f"file-{uuid.uuid4().hex[:8]}"
        self.files[file_id] = FakeFile(
            id=file_id,
            name=body["name"],
            mime_type=body.get("mimeType", "application/octet-stream"),
            parents=body.get("parents", []),
            app_properties=body.get("appProperties", {}),
        )
        return httpx.Response(200, json={"id": file_id})

    def _file(self, request: httpx.Request) -> httpx.Response:
        file_id = request.url.path.rsplit("/", 1)[1]
        file = self.files.get(file_id)
        if file is None:
            return httpx.Response(404, json={"error": {"message": "not found"}})
        if request.method == "DELETE":
            file.trashed = True
            return httpx.Response(204)
        if request.url.params.get("alt") == "media":
            return httpx.Response(200, content=file.content)
        return httpx.Response(200, json={"id": file.id, "name": file.name})

    def _upload(self, request: httpx.Request) -> httpx.Response:
        upload_type = request.url.params.get("uploadType")
        tail = request.url.path[len("/upload/drive/v3/files") :].lstrip("/")
        file_id = tail or None

        if upload_type == "resumable":
            body = json.loads(request.content)
            upload_id = uuid.uuid4().hex[:8]
            self.sessions[upload_id] = ResumableSession(
                upload_id=upload_id,
                file_id=file_id,
                name=body["name"],
                parent=(body.get("parents") or [""])[0],
                mime_type=request.headers.get("X-Upload-Content-Type", ""),
                app_properties=body.get("appProperties", {}),
                total=int(request.headers.get("X-Upload-Content-Length", 0)),
            )
            return httpx.Response(
                200, headers={"Location": f"https://upload.test/resumable/{upload_id}"}
            )

        # multipart
        self.uploads += 1
        raw = request.content
        head, _, payload = raw.partition(b"\r\n\r\n")
        meta_blob, _, rest = payload.partition(b"\r\n--")
        try:
            metadata = json.loads(meta_blob)
        except json.JSONDecodeError:
            metadata = {}
        content = rest.partition(b"\r\n\r\n")[2].rpartition(b"\r\n--")[0]
        assert head is not None

        if file_id and file_id in self.files:
            existing = self.files[file_id]
            existing.content = content
            existing.name = metadata.get("name", existing.name)
            existing.app_properties = metadata.get("appProperties", existing.app_properties)
            return httpx.Response(200, json={"id": file_id})

        new_id = f"file-{uuid.uuid4().hex[:8]}"
        self.files[new_id] = FakeFile(
            id=new_id,
            name=metadata.get("name", "unnamed"),
            mime_type="application/octet-stream",
            parents=metadata.get("parents", []),
            app_properties=metadata.get("appProperties", {}),
            content=content,
        )
        return httpx.Response(200, json={"id": new_id})

    def _resumable_chunk(self, request: httpx.Request) -> httpx.Response:
        upload_id = request.url.path.rsplit("/", 1)[1]
        session = self.sessions.get(upload_id)
        if session is None:
            return httpx.Response(404, json={"error": {"message": "session gone"}})

        content_range = request.headers.get("Content-Range", "")

        # `bytes */total` is a status probe, not a data chunk.
        if content_range.startswith("bytes */"):
            if not session.received:
                return httpx.Response(308, headers={})
            return httpx.Response(308, headers={"Range": f"bytes=0-{len(session.received) - 1}"})

        self._chunks_served += 1
        if self.fail_chunk_after is not None and self._chunks_served > self.fail_chunk_after:
            return httpx.Response(503, json={"error": {"message": "backend hiccup"}})

        match = re.match(r"bytes (\d+)-(\d+)/(\d+)", content_range)
        assert match, f"bad Content-Range: {content_range}"
        start, _end, total = (int(g) for g in match.groups())

        session.received[start:] = request.content

        if len(session.received) >= total:
            file_id = session.file_id or f"file-{uuid.uuid4().hex[:8]}"
            self.files[file_id] = FakeFile(
                id=file_id,
                name=session.name,
                mime_type=session.mime_type,
                parents=[session.parent] if session.parent else [],
                app_properties=session.app_properties,
                content=bytes(session.received),
            )
            self.uploads += 1
            return httpx.Response(200, json={"id": file_id})

        return httpx.Response(308, headers={"Range": f"bytes=0-{len(session.received) - 1}"})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)
