# C1 — Google Drive export

**Phase:** 1 · **Skill:** `.claude/skills/drive-export` · **Service:** `backend/app/services/storage.py`

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

- Scope: `https://www.googleapis.com/auth/drive.file` — access limited to files this
  app created. Never request full `drive` scope; the app has no legitimate need to
  read the user's other files, and the reduced blast radius is worth the constraint.
- Refresh token persisted with `0600` permissions outside the repo tree.
- Flow: `GET /api/v1/drive/oauth/start` → Google consent → `GET /api/v1/drive/oauth/callback`.
- Redirect URI must match `GOOGLE_OAUTH_REDIRECT_URI` byte-for-byte including trailing
  slash, or Google returns `redirect_uri_mismatch`.

## Interface

```python
class StorageService(Protocol):
    async def ensure_meeting_folder(self, meeting: Meeting) -> str: ...
    async def export(self, meeting: Meeting, artifact: Artifact) -> ExportResult: ...
    async def export_all(self, meeting: Meeting) -> ExportManifest: ...
    async def read_manifest(self, meeting_id: str) -> ExportManifest | None: ...
```

`StubStorageService` writes the same tree to `MEDIA_ROOT/drive-stub/`, so the folder
contract and idempotency logic are exercised offline.

## Acceptance criteria

- [ ] Fresh export produces the full folder tree with correct naming
- [ ] Re-export performs zero writes when nothing changed
- [ ] Re-export after editing one artifact writes only that artifact
- [ ] Killing the process mid-audio-upload and restarting resumes, not restarts
- [ ] Deleting the local database and re-syncing reconstructs export state from Drive
- [ ] Rate-limit response triggers backoff, not failure
- [ ] Every meeting folder contains the privacy README
- [ ] Filenames with `/`, emoji, and 300-char titles are handled

## Failure modes

| Failure | Behaviour |
|---------|-----------|
| Token expired | Refresh silently; if refresh fails, surface a re-auth prompt |
| Quota exceeded | Backoff, then record failed manifest entry; do not lose the artifact |
| Folder deleted by user | Recreate; log a warning; re-upload from local staging if available |
| Duplicate folder names (same title, same day) | Suffix with a short meeting-id prefix |
| Network loss mid-upload | Resumable session persists; next run continues |
