# C1 — Google Drive export

**Phase:** 1 · **Status:** implemented · **Skill:** `.claude/skills/drive-export`
**Services:** `backend/app/services/{google_auth,drive_client,drive_storage}.py`

## Intent

Get every recording and every derived artifact into a Drive folder the user owns,
in a structure a human can navigate without this software. This is the foundation
capability — everything else assumes the raw material is safe.

The design goal is *boring*. No cleverness, no surprises, no data loss.

## Folder contract

```
Pocket.ai Studio/                          ← DRIVE_ROOT_FOLDER_NAME
├── 2026/
│   ├── 2026-07-29 — Platform Architecture Review/
│   │   ├── audio.m4a                      original, untouched
│   │   ├── transcript.md                  speaker-attributed, readable
│   │   ├── transcript.json                structured, with spans
│   │   ├── summary.md
│   │   ├── action-items.md
│   │   ├── mind-map.md                    Mermaid
│   │   ├── deck.pptx                      when generated
│   │   ├── manifest.json                  export state
│   │   └── README.md                      privacy notice
│   └── 2026-07-30 — Weekly 1:1 with Priya/
└── _speakers/                             voiceprint metadata only, never embeddings
```

Folder name: `{YYYY-MM-DD} — {title}`, with `/` and control characters stripped and
the title truncated to 120 chars. Em-dash separator because it is unambiguous and
sorts cleanly.

## Behavioural requirements

**Idempotency.** Keyed on `(meeting_id, artifact_kind)`. Re-running an export updates
the existing Drive file in place via its file id. It must never create
`transcript (2).md`. If the file id is missing from the manifest, look it up by name
within the meeting folder before creating.

**Resumability.** Audio files can be hundreds of megabytes. Use Drive's resumable
upload session; persist the session URI in the manifest. A process killed mid-upload
resumes from the last confirmed byte on the next run.

**Content-hash skip.** Each manifest entry stores the artifact's content hash. If the
hash is unchanged, skip the upload entirely. Re-running a full export on an unchanged
meeting should perform zero writes.

**Manifest in Drive.** `manifest.json` is written to the meeting folder, not just the
database. It carries `meeting_id`, and per artifact: kind, drive file id, content
hash, size, exported timestamp. This is what makes database loss recoverable.

**Backoff.** Drive returns 403 rate-limit and 500-class errors under load. Exponential
backoff with jitter, capped at 5 attempts. Persistent failure records a manifest entry
with `status: failed` and a reason, so a later run retries rather than silently skipping.

**Privacy notice.** Every meeting folder gets a `README.md` stating that it contains
a recording of other people and should not be shared without their agreement. Placed
where someone is about to make the mistake, not buried in settings.

## OAuth

Implemented directly against Google's endpoints (`google_auth.py`) rather than through
`google-auth-oauthlib` — the flow is small, the endpoints are stable, and this keeps the
service layer async instead of bolting a synchronous client onto a thread pool.

- **Scope: `drive.file`** — files this app created, nothing else. Never full `drive`.
- **PKCE (S256)** on every authorization. Binds the code to this request, so a code
  intercepted from the redirect cannot be redeemed without the verifier.
- **`state` CSRF check.** Without it an attacker can hand the user a callback URL
  carrying *their* code, silently pointing exports at an attacker-controlled Drive.
  Single-use; expires after 10 minutes.
- **`access_type=offline` + `prompt=consent`.** Both are required, or a re-authorizing
  account gets an access token with no refresh token and unattended export dies an
  hour later.
- **Refresh never clobbers the stored refresh token.** Google omits it on refresh
  responses; taking `.get()` without a fallback destroys the durable grant.
- **Token file `0600`, directory `0700`, outside the repo tree.** Written via a private
  temp file and `os.replace`, so a crash cannot leave a truncated token and the secret
  is never briefly world-readable.
- Redirect URI must match `GOOGLE_OAUTH_REDIRECT_URI` byte-for-byte including trailing
  slash, or Google returns `redirect_uri_mismatch`.

| Route | Purpose |
|-------|---------|
| `GET /api/v1/drive/oauth/start` | Redirect to consent (`?redirect=false` for JSON) |
| `GET /api/v1/drive/oauth/callback` | Exchange the code; renders a result page |
| `POST /api/v1/drive/oauth/revoke` | Revoke at Google, then drop the local token |
| `GET /api/v1/drive/status` | Backend, scope, authorization state, live `check()` |

## Recovery metadata

Every file and folder carries `appProperties`: `pocketAiStudio` (role), `meetingId`,
and for artifacts `artifactKind`. This is what makes recovery efficient — the meeting
folder is found by a metadata query, not by walking the tree — and it is why the
"database loss is recoverable" claim is real rather than aspirational.

## Interface

```python
class StorageService(Protocol):
    async def ensure_meeting_folder(self, meeting: Meeting) -> str: ...
    async def export(self, meeting: Meeting, artifact: Artifact) -> ExportResult: ...
    async def export_all(self, meeting: Meeting) -> ExportManifest: ...
    async def read_manifest(self, meeting_id: str) -> ExportManifest | None: ...
```

`StubStorageService` writes the same tree to `MEDIA_ROOT/drive-stub/`, so the folder
contract and idempotency logic are exercised offline with no credentials at all.

`DriveStorageService` implements the same protocol against Drive. Tests drive the real
client through an in-memory Drive (`tests/fake_drive.py`) over `httpx.MockTransport`, so
query building, multipart and resumable uploads, 308 continuation, backoff, and token
refresh all run as production code paths without a network.

## Acceptance criteria

Covered by `tests/test_drive_export.py` and `tests/test_google_auth.py`:

- [x] Fresh export produces the full folder tree with correct naming
- [x] Re-export performs **zero** writes when nothing changed — manifest included
- [x] Re-export after editing one artifact writes only that artifact (plus manifest)
- [x] Interrupted resumable upload persists its session and resumes from the offset
- [x] A dead session restarts cleanly rather than failing
- [x] Export state reconstructs from Drive alone, with no database
- [x] Rate-limit 403 / 429 / 5xx trigger backoff; permission 403 fails fast
- [x] A 401 mid-flight refreshes once and retries
- [x] Every meeting folder contains the privacy README
- [x] Titles with apostrophes are query-escaped (`Priya's 1:1`)
- [x] Same-day title collisions are disambiguated by meeting-id suffix
- [x] A retitled meeting reuses its existing folder
- [x] One failing artifact does not abandon the rest
- [x] A previously failed artifact is retried on the next run
- [x] Corrupt manifest does not block export
- [ ] Verified against a real Google account *(needs a Cloud Console OAuth client)*

## Failure modes

| Failure | Behaviour |
|---------|-----------|
| Token expired | Refresh silently; if refresh fails, surface a re-auth prompt |
| Quota exceeded | Backoff, then record failed manifest entry; do not lose the artifact |
| Folder deleted by user | Recreate; log a warning; re-upload from local staging if available |
| Duplicate folder names (same title, same day) | Suffix with a short meeting-id prefix |
| Network loss mid-upload | Resumable session persists; next run continues |
