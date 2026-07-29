# Architecture

## Shape of the system

A pipeline, not a monolith of features. Audio enters once, and each stage adds a
layer of structure that later stages consume. Every stage is independently
re-runnable against stored inputs, which matters enormously: when the summarizer
improves, you re-summarize three years of meetings without re-uploading a byte.

```
Pocket.ai device
      │  audio + raw transcript
      ▼
┌─────────────┐
│   INGEST    │  normalize audio, validate quality, assign meeting_id
└──────┬──────┘
       │
       ├──────────────────────────────► ┌──────────────┐
       │                                │ DRIVE EXPORT │ ──► Google Drive
       │                                └──────────────┘     (system of record)
       ▼
┌─────────────┐
│ DIARIZATION │  anonymous turns  ──►  IDENTIFICATION  ──► named speakers
└──────┬──────┘                         (voiceprint library + manual tags)
       │  attributed transcript
       ▼
┌──────────────────────────────────────────────────────┐
│                    ENRICHMENT                        │
│  summaries · action items · mind maps · decisions    │
│  every output carries TranscriptSpan citations       │
└──────┬───────────────────────────────────┬───────────┘
       │                                   │
       ▼                                   ▼
┌─────────────┐                    ┌───────────────┐
│  INDEXING   │ ──► vector store   │   ARTIFACTS   │ ──► Drive
│  (chunks +  │                    │ md · mermaid  │
│   metadata) │                    │ pptx · json   │
└──────┬──────┘                    └───────────────┘
       │
       ├──────────────► CHAT (RAG over corpus)
       ├──────────────► SLIDE GENERATION (structure → render)
       └──────────────► EXECUTIVE COACH (longitudinal rubric scoring)
```

## Why this shape

**Stages are checkpointed, not streamed.** Each stage writes its output to storage
before the next reads it. Slower than a streaming pipeline and far easier to reason
about: you can inspect the intermediate state, re-run one stage in isolation, and
recover from a crash without redoing expensive work. Diarization on an hour of
audio is minutes of GPU time — you do not want to redo it because the summarizer
threw.

**Diarization and identification are separate stages.** Diarization ("there are
three voices, here are their turns") is an audio-signal problem. Identification
("voice 2 is Priya") is a matching problem against an enrolled library. Splitting
them means the expensive audio pass runs once and identification can be re-run
cheaply whenever the voiceprint library grows or the user corrects a label.

**Indexing is downstream of identification.** Chunks carry speaker names as
metadata, which is what makes "what did Priya commit to" a filterable query rather
than a semantic-similarity guess.

**Export is a fan-out, not a terminal stage.** Drive export runs immediately after
ingest (so raw material is safe before anything can fail) and again after each
enrichment (so derived artifacts land alongside their source).

## Layers

### `backend/app/models/` — domain model

Pydantic v2 value objects. This is the shared vocabulary; every service speaks it.
`TranscriptSpan` is the load-bearing type — it is how every generated claim points
back at its evidence.

### `backend/app/services/` — capability implementations

Each capability is a protocol in `protocols.py` with at least two implementations:
a stub that runs offline with deterministic output, and a real one behind an
optional dependency extra. The stub is not a test fixture — it is a first-class
implementation that keeps the whole system runnable without credentials.

```python
class DiarizationService(Protocol):
    async def diarize(self, audio: AudioRef) -> list[SpeakerTurn]: ...


class StorageService(Protocol):
    async def export(self, meeting: Meeting, artifact: Artifact) -> ExportResult: ...


class LLMService(Protocol):
    async def complete(self, prompt: Prompt, *, model: ModelTier) -> str: ...
```

Selection happens in `services/registry.py`, driven by config. Nothing else in the
codebase imports a concrete implementation.

### `backend/app/api/routes/` — HTTP surface

Thin. Validate, delegate to a service, serialize. No business logic. Routes are
grouped by resource (`meetings`, `drive`, `speakers`, `insights`, `chat`, `coach`).

### `backend/app/agents/` — multi-step reasoning

Where a capability needs planning rather than a single LLM call — slide generation
and the executive coach — the logic lives here as an explicit multi-step procedure
rather than one giant prompt. Slide generation is the clearest case: *derive the
governing thought → build the MECE tree → write action titles → select evidence per
slide → render*, with the structure reviewable before rendering.

## Data flow contracts

| Stage | Input | Output | Idempotency key |
|-------|-------|--------|-----------------|
| Ingest | audio file + raw transcript | `Meeting`, `AudioRef` | content hash of audio |
| Export | `Meeting` + `Artifact` | `ExportResult` (Drive file id) | `(meeting_id, artifact_kind)` |
| Diarize | `AudioRef` | `list[SpeakerTurn]` | `audio_hash` |
| Identify | turns + voiceprints | `list[SpeakerTurn]` with `speaker_id` | `(audio_hash, library_version)` |
| Enrich | attributed transcript | `MeetingInsights` | `(meeting_id, prompt_version)` |
| Index | transcript + insights | vector store entries | `(meeting_id, chunk_id)` |

Including `prompt_version` and `library_version` in idempotency keys is deliberate:
improving a prompt should invalidate the cache and trigger reprocessing, not
silently serve stale output.

## Storage split

**Google Drive — artifacts.** Audio, transcripts, summaries, mind maps, decks.
Human-browsable, user-owned, portable. See
[ADR-0002](adr/0002-drive-as-system-of-record.md).

**Postgres — metadata and relations.** Meetings, speakers, action items, export
manifests, coaching scores. Small, queryable, rebuildable from Drive in the worst case.

**Vector store — retrieval index.** Transcript chunks with speaker/time metadata.
Pure derived data; safe to drop and rebuild.

**Local disk (`MEDIA_ROOT`) — staging and voiceprints.** Audio in flight, and
speaker embeddings. Voiceprints never leave local infrastructure.

## Model routing

Two tiers, chosen per task rather than globally:

- **Fast tier** (`claude-haiku-4-5-20251001`) — high-volume mechanical passes:
  chunk-level extraction, classification, span validation, first-pass action item
  detection.
- **Reasoning tier** (`claude-opus-5`) — synthesis where quality compounds:
  executive summaries, slide structure, coaching analysis, cross-meeting insight.

Routing is config, not code. A capability declares the tier it needs; the registry
resolves it. This keeps a long-corpus operation affordable without hard-coding
model names across the codebase.

## Failure posture

- **Ingest fails** → nothing else runs; the recording is quarantined with a reason.
- **Export fails** → retried with backoff; the manifest records the failure so a
  later run resumes rather than restarts.
- **Diarization fails** → degrade to unattributed transcript. Summaries still work;
  they just cannot say who said what. Manual tagging remains available.
- **An enrichment fails** → the others still land. `MeetingInsights` is partial by
  design, with per-section status.
- **LLM returns an uncitable claim** → the claim is dropped in validation, not
  surfaced. Better a shorter summary than a wrong one.

## What is deliberately not here

- No message queue in v1. Stages run in-process via FastAPI background tasks. The
  volume — a few meetings a day — does not justify the operational cost. The stage
  boundaries are drawn so a queue can be dropped in later without reshaping the code.
- No auth/multi-tenancy. Single user, local deployment.
- No real-time layer. Everything is post-hoc.
