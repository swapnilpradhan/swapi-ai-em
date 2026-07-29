# ADR-0005: Every external dependency has a first-class stub

**Status:** Accepted · **Date:** 2026-07-29

## Context

This system depends on Google Drive OAuth, an LLM provider, pyannote (which pulls in
torch — gigabytes of dependencies plus a HuggingFace license acceptance), and a
vector store. Any one of these is enough friction to stall a development session.
All four together mean that a new environment cannot run the application at all
until every credential is provisioned.

That friction compounds badly: CI needs secrets, tests become slow and flaky, and —
most damagingly — the architecture drifts toward whatever the integrations make
convenient, because nobody can run the system without them to notice.

## Decision

**Every external dependency sits behind a Protocol with at least two implementations:
a real one and a stub. The stub is production-quality code, not a test fixture.**

```python
class DiarizationService(Protocol):
    async def diarize(self, audio: AudioRef) -> list[SpeakerTurn]: ...

# services/diarization.py
class StubDiarizationService:      # deterministic, offline, always available
class PyannoteDiarizationService:  # real, behind the `audio` extra
```

Rules:

1. **Stubs produce deterministic, structurally valid output.** Not empty lists, not
   `NotImplementedError`. `StubDiarizationService` returns plausible turns derived
   from transcript structure. `StubLLMService` returns well-formed, correctly cited
   responses derived from the input. Every downstream stage gets exercised.
2. **The full pipeline runs on stubs with zero credentials**, end to end, from ingest
   to artifact.
3. **The test suite runs against stubs only.** No network, no API keys, no GPU.
   Fast and deterministic.
4. **Real implementations live behind optional dependency extras.** `uv sync --extra dev`
   installs nothing heavy. torch arrives only when someone asks for `--extra audio`.
5. **Selection is config-driven** in `services/registry.py`. No other module imports
   a concrete implementation.

## Consequences

**Good**
- A new environment is productive in one command.
- CI needs no secrets and stays fast.
- The seams stay honest. It is impossible to accidentally couple a service to a
  provider-specific detail when a stub must satisfy the same interface.
- Integrations can be built and swapped independently.
- Demos and frontend work do not burn API budget.

**Bad**
- Real maintenance cost — every interface change means updating stubs too.
- Stubs can drift from real behavior and hide integration bugs. Mitigated by
  integration tests that run against real services on demand (not in the default suite).
- Stub output can look convincing enough to be mistaken for real results. Mitigated by
  a visible banner in API responses when a stub backend is active.

**Neutral**
- Slightly more indirection than importing a client directly. Worth it.

## Alternatives considered

**Mock in tests only.** The common approach. Rejected because the application still
cannot *run* without credentials — only the tests can. That is where architectural
drift creeps in.

**Record/replay fixtures (VCR-style).** Good fidelity for HTTP, useless for torch-based
local inference, and the cassettes contain real meeting data — which is exactly the
data we must not commit.

**Make everything optional with graceful no-ops.** Produces a system that appears to
work while doing nothing, which is a worse failure than a clear stub.
