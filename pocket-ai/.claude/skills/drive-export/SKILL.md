---
name: drive-export
description: Export Pocket.ai meeting audio, transcripts, and derived artifacts to Google Drive with a deterministic folder tree, idempotent writes, and a recoverable manifest. Use this skill whenever the user mentions exporting, syncing, backing up, or uploading meetings, recordings, transcripts, or artifacts to Drive — and also when they are debugging duplicate files, stalled uploads, OAuth errors, or missing meeting folders. Use it before implementing any new artifact type, since every artifact must have a defined place in the folder contract.
---

# Drive export

Read [`docs/capabilities/01-drive-export.md`](../../../docs/capabilities/01-drive-export.md)
for the full contract and [ADR-0002](../../../docs/adr/0002-drive-as-system-of-record.md)
for why Drive is the system of record rather than a backup target.

## The one thing to keep in mind

Drive is not a backup — it is the archive that outlives this application. That single
framing decides most questions. If you are wondering whether an artifact should be
human-readable, whether a filename should be cryptic, or whether state should live only
in the database: assume the app is gone in five years and the user is looking at the
folder. Optimize for that person.

## Folder contract

```
{DRIVE_ROOT_FOLDER_NAME}/
└── {YYYY}/
    └── {YYYY-MM-DD} — {title}/
        ├── audio.{ext}          original, untouched
        ├── transcript.md        speaker-attributed, readable
        ├── transcript.json      structured, with spans
        ├── summary.md
        ├── action-items.md
        ├── mind-map.md          Mermaid
        ├── deck.pptx            when generated
        ├── manifest.json        export state
        └── README.md            privacy notice
```

Folder naming: strip `/` and control characters, collapse whitespace, truncate the
title to 120 chars. On a same-day title collision, suffix with the first 8 chars of
`meeting_id`.

Adding a new artifact type means adding it here first. An artifact with no defined
place ends up dumped at the folder root with an invented name, and the contract erodes.

## Non-negotiables

**Idempotency.** Key on `(meeting_id, artifact_kind)`. Update in place via Drive file
id. If the id is missing from the manifest, look the file up by name inside the meeting
folder *before* creating anything. `transcript (2).md` appearing in a user's archive is
the failure this whole design exists to prevent.

**Content-hash skip.** Each manifest entry carries the artifact's content hash. Unchanged
hash means skip the upload entirely. A full re-export of an unchanged meeting should
perform zero writes — verify this, because it is the cheapest possible regression test
for the idempotency logic.

**Resumable uploads.** Audio runs to hundreds of megabytes. Use Drive's resumable upload
session and persist the session URI in the manifest before starting. A process killed
mid-upload must resume, not restart.

**Manifest lives in Drive.** Write `manifest.json` to the meeting folder, not only to
the database. This is what makes the "database loss is recoverable" claim real. If you
find yourself writing export state only to Postgres, stop — you have broken the property
that justifies the architecture.

**Backoff, then record.** Drive returns 403 rate-limit and 500-class errors under load.
Exponential backoff with jitter, 5 attempts. On persistent failure write a manifest entry
with `status: failed` and the reason, so the next run retries. Never silently skip.

**Privacy README.** Every meeting folder gets one, stating the folder contains recordings
of other people and should not be shared without their agreement. It goes in the folder
because that is where someone is about to make the mistake.

## OAuth

Scope is `drive.file` — files this app created, nothing else. Do not request full `drive`
scope; the app has no legitimate reason to read the user's other documents, and the
reduced blast radius is worth the constraint. If something seems to need broader scope,
that is a signal the design is wrong, not that the scope should widen.

Refresh token: `0600`, outside the repo tree, never logged.

Redirect URI must match `GOOGLE_OAUTH_REDIRECT_URI` byte-for-byte including any trailing
slash. `redirect_uri_mismatch` is almost always this.

## Working on this

Implement against `StorageService` in `backend/app/services/protocols.py`. `StubStorageService`
writes the identical tree to `MEDIA_ROOT/drive-stub/`, which means folder naming,
idempotency, manifest handling, and hash-skip logic are all testable offline. Get the
behavior right against the stub first; the Drive client should then be a thin adapter
with no logic of its own.

## Checklist before calling it done

- [ ] Fresh export produces the full tree with correct naming
- [ ] Re-export of unchanged meeting performs zero writes
- [ ] Editing one artifact re-uploads only that artifact
- [ ] Kill mid-upload, restart, resumes from last confirmed byte
- [ ] Delete the local DB, re-sync, export state reconstructs from Drive
- [ ] Rate-limit response backs off rather than failing
- [ ] Titles with `/`, emoji, and 300 characters are handled
- [ ] Every meeting folder has the privacy README
