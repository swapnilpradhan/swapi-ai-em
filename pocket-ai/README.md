# Pocket.ai Studio

Meeting intelligence and executive coaching built on top of Pocket.ai recordings.

Pocket.ai captures the audio and a raw transcript. This project owns everything
that happens next: getting the artifacts into Google Drive where you actually
keep them, turning a wall of text into something you can act on, and using the
accumulated corpus of how you speak and write to make you a sharper executive
communicator.

## What it does

**Capture & durability**
- Webhook-driven ingest from the Pocket API — no manual export step. Idempotent under
  at-least-once delivery, with history backfill through the same path.
- Export audio + transcripts to Google Drive on a predictable folder and naming
  scheme, with idempotent re-runs and a manifest so nothing is exported twice.

**Understanding**
- Speaker identification — putting names to Pocket's anonymous "Speaker 1" labels,
  learned from a voiceprint library you build once and reuse forever. Diarization is
  skipped when the source already separated the voices.
- Structured summaries at three altitudes: one-line, executive paragraph, full brief.
- Action items with owner, due date, and confidence — extracted with span citations
  back into the transcript.
- Mind maps of how a discussion actually branched.

**Leverage**
- Chat with one transcript, one meeting series, or your whole corpus (RAG over
  transcript chunks with speaker and time metadata).
- Consulting-grade slide generation — MECE structure, pyramid principle,
  action-titled slides in the house styles of the major strategy firms.

**Personal development**
- An executive coach that reads your actual speech and writing, scores it against
  an executive communication rubric, and runs a longitudinal development program
  across written English, spoken English, thought leadership, and thought development.

## Status

Phase 1 in progress.

- **Ingest** — webhook-driven pull from the Pocket API, built end to end, but against an
  **unverified** reading of that API (see the note below).
- **Drive export** — real OAuth (PKCE, `drive.file` scope) and a full Drive v3 client
  with resumable uploads, idempotency, and manifest recovery. Complete and covered by
  offline tests; not yet run against a live Google account. See
  [`docs/SETUP_DRIVE.md`](docs/SETUP_DRIVE.md).
- **Everything downstream** (RAG, slide rendering, coaching) sits behind service
  interfaces with working stubs.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for what lands when.

## Quick start

```bash
cd pocket-ai
cp .env.example .env          # fill in what you have; stubs cover the rest
uv sync --extra dev
uv run pytest                 # should be green
make dev                      # http://localhost:8000/docs
```

The frontend is a separate app:

```bash
cd frontend && npm install && npm run dev   # http://localhost:3000
```

## Layout

```
pocket-ai/
├── docs/                  Planning: PRD, architecture, data model, ADRs, capability specs
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── ROADMAP.md
│   ├── SECURITY_PRIVACY.md
│   ├── SETUP_DRIVE.md     Connecting a real Google account
│   ├── adr/               Architecture decision records
│   └── capabilities/      One spec per feature — the contract each skill implements
├── .claude/skills/        Claude Code skills, one per capability
├── backend/app/
│   ├── models/            Pydantic domain model — the shared vocabulary
│   ├── services/          Capability implementations behind protocols
│   │                      pocket.py · webhooks.py · sync.py — the ingest path
│   │                      google_auth.py · drive_client.py · drive_storage.py — export
│   ├── api/routes/        HTTP surface
│   └── core/              Config, logging
├── frontend/              Next.js app
└── tests/
```

## Design commitments

These are load-bearing; read [`docs/adr/`](docs/adr/) before changing them.

1. **Google Drive is the system of record for artifacts.** The database stores
   metadata and pointers, never the only copy of your audio. If this project
   disappears, your Drive folder is still a complete, human-browsable archive.
2. **Every generated claim cites its source span.** Summaries, action items, and
   coaching feedback carry `TranscriptSpan` references. No unsourced assertions.
3. **Capabilities are services behind protocols.** Diarization, LLM, storage, and
   vector search each have a stub implementation so the whole system runs — and
   is testable — with zero credentials.
4. **Local-first for sensitive audio.** Voiceprints and raw audio never leave your
   infrastructure unless you explicitly export them.
5. **Webhook payloads are not trusted.** A delivery supplies a recording id; the
   content is always re-fetched from the API. Signature verification fails closed.

> **Note:** the Pocket API specifics (endpoint paths, field names, signature scheme,
> event names) are **unverified** — the docs site blocks automated fetching. They are
> centralized in four places so correcting them is a contained edit. Work the checklist
> in [`docs/capabilities/00-pocket-ingest.md`](docs/capabilities/00-pocket-ingest.md)
> against a real API key before relying on this.

## Extracting to a standalone repo

This lives as a subdirectory for now. To split it out once you have an empty repo:

```bash
git subtree split --prefix=pocket-ai -b pocket-ai-standalone
git push git@github.com:<you>/pocket-ai-studio.git pocket-ai-standalone:main
```
