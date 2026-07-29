# ADR-0002: Google Drive is the system of record for artifacts

**Status:** Accepted · **Date:** 2026-07-29

## Context

The system produces audio files, transcripts, summaries, mind maps, and decks. These
need to live somewhere durable. The obvious engineering choice is object storage
(S3/GCS) with the app as the access layer, and Drive export as an optional
convenience feature.

But the user's stated requirement was Drive, and thinking about why exposes something
important: this is a personal knowledge archive with a multi-decade horizon. The
application is far more likely to be abandoned, rewritten, or replaced than the
archive is to stop mattering. An architecture where the artifacts are only reachable
through this app is an architecture that traps its own data.

## Decision

**Google Drive is the system of record for artifacts. The database holds metadata
and pointers.**

Concretely:

1. Drive's folder structure is designed for a human with no software:
   ```
   Pocket.ai Studio/
     2026/
       2026-07-29 — Platform Architecture Review/
         audio.m4a
         transcript.md          (speaker-attributed, readable)
         summary.md
         action-items.md
         mind-map.md            (Mermaid, renders in most viewers)
         deck.pptx
         manifest.json
         README.md              (privacy notice)
   ```
2. Every artifact is written in a format that opens without this app: Markdown,
   Mermaid, pptx, standard audio codecs. No proprietary serialization, no pickled
   Python, no database-only representations.
3. `manifest.json` lives in Drive, not only in the database. It carries enough state
   to reconstruct export status after total database loss.
4. The database is treated as a rebuildable cache. Losing it is an inconvenience
   (re-index, re-derive), not a data loss event.

## Consequences

**Good**
- The archive outlives the application. That is the whole point.
- Users already have Drive backup, sync, search, sharing, and mobile access — all
  features we would otherwise have to build badly.
- Zero storage cost to the project.
- Debugging is trivial: open the folder and look.

**Bad**
- Drive API constraints become our constraints: quota limits, rate limits, eventual
  consistency on folder listings, and no transactions. Export logic must be
  idempotent and resumable — which is real complexity we are choosing to take on.
- Drive is not a database. Anything needing indexed query (corpus chat, coaching
  trends) must be mirrored into Postgres and the vector store, so some data is
  duplicated by design.
- Large audio uploads are slow and failure-prone, requiring resumable upload support.
- Dependency on a Google account and on API stability.

**Neutral**
- Forces artifact formats to be human-readable, which is a discipline worth having
  regardless.

## Alternatives considered

**S3/GCS as the record, Drive as an export target.** Better engineering ergonomics —
transactions, consistency, no quota. Rejected because it makes the app the gatekeeper.
The archive would be an implementation detail of software that will not last as long
as the data.

**Local filesystem as the record.** Fastest, fully private, no API. Rejected because
it has no redundancy, no mobile access, and no sync — a disk failure loses everything.

**Both, with Drive mirroring S3.** Two systems of record is zero systems of record.
Reconciliation logic would be a permanent source of bugs.

**Drive for everything including metadata.** Tempting for purity. Rejected because
querying "every action item assigned to me in the last quarter" against a folder of
JSON files is unworkable at any real scale.
