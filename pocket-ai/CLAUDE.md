# Pocket.ai Studio — working notes for Claude

## What this is

Post-processing platform for Pocket.ai meeting recordings: Drive export, speaker
identification, summarization, action items, mind maps, transcript chat,
consulting-style slides, and an executive communication coach.

Read `docs/PRD.md` for product intent and `docs/ARCHITECTURE.md` for how the
pieces fit. Each feature has a spec in `docs/capabilities/` — that spec is the
contract, and the matching skill in `.claude/skills/` is how you execute it.

## Ground rules

- **The domain model in `backend/app/models/` is the shared vocabulary.** Add
  fields there rather than passing loose dicts between services. If two services
  disagree about what a "meeting" is, the model is wrong.
- **Never invent content that isn't in the transcript.** Summaries, action items,
  and insights must carry `TranscriptSpan` citations. If the transcript doesn't
  support a claim, drop the claim — do not soften it into a plausible-sounding
  generality.
- **Services sit behind protocols** (`backend/app/services/protocols.py`). Every
  one has a stub. Tests run against stubs; nothing in the test suite should need
  a network call or an API key.
- **Audio and voiceprints are sensitive.** They stay under `MEDIA_ROOT` or in the
  user's own Drive. Don't add code paths that ship them to third parties, and
  don't log transcript content at INFO.
- **Drive writes are idempotent.** Key on `(meeting_id, artifact_kind)`. Re-running
  an export updates in place; it never creates `transcript (2).md`.

## Conventions

- Python 3.11+, `uv` for dependency management, `ruff` for lint and format.
- Async throughout the service layer; sync only where a library forces it.
- Pydantic v2 models, `model_config = ConfigDict(frozen=True)` for value objects.
- Optional heavy dependencies (torch, chromadb, google-api-client) live in
  `[project.optional-dependencies]` extras. Guard imports so the base install runs.
- Tests: `uv run pytest`. Keep them fast and offline.

## Where things go

| I want to...                        | Go to                                            |
|-------------------------------------|--------------------------------------------------|
| Change what a meeting record holds  | `backend/app/models/meeting.py`                   |
| Add an export target                | `backend/app/services/storage.py`                 |
| Change how speakers are identified  | `backend/app/services/diarization.py`             |
| Change summary shape or prompt      | `backend/app/services/insights.py` + capability spec |
| Add an API endpoint                 | `backend/app/api/routes/`                         |
| Change coaching rubric              | `docs/capabilities/08-executive-coach.md`         |

## Gotchas

- `DIARIZATION_BACKEND=stub` is the default. Real pyannote needs `HUGGINGFACE_TOKEN`
  *and* accepting the model license on the HF model page — a missing license
  acceptance fails with an opaque 401.
- Google Drive OAuth needs the redirect URI registered in Cloud Console to match
  `GOOGLE_OAUTH_REDIRECT_URI` byte-for-byte, trailing slash included.
- **Pocket returns an optional `speaker` per segment.** When present the pipeline
  skips diarization entirely (`SKIPPED`, not failed) and runs identification only.
  Whether it is reliably populated is the highest-value open question in the project —
  if it is, pyannote/torch/GPU leave entirely. See ADR-0008.
- `speaker` becomes `speaker_label`, never `speaker_id`. Upstream says which *voice*,
  not which *person*.
- Timestamp drift and the `[00:01:23]` regex parser only ever applied to hand-exported
  text. The API returns numeric timings — that gotcha is not on the primary path.
- Webhook development needs a public URL (`cloudflared tunnel --url http://localhost:8000`),
  or use `POST /api/v1/pocket/pull` which runs the identical path.
