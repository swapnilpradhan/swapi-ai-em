# Security and privacy

This system records other people. That single fact makes privacy a design
constraint rather than a compliance checkbox, and it drives several architectural
decisions that would otherwise look like over-engineering.

## Threat model

**What we are protecting**
- Raw meeting audio — the most sensitive asset. Contains everything said in the room,
  including material never intended for durable capture.
- Voiceprints — biometric identifiers. In several jurisdictions these are a special
  category of personal data (BIPA in Illinois, GDPR Art. 9 in the EU).
- Transcripts and derived artifacts — commercially sensitive; often contain
  compensation, personnel, and strategy discussion.
- OAuth refresh tokens — grant durable access to the user's entire Drive.

**Who we are protecting it from**
- Accidental disclosure through over-broad Drive sharing.
- Third-party model providers receiving more than necessary.
- Anyone with filesystem access to the deployment host.
- The user's own future self, exporting a folder without realizing what is in it.

**Explicitly out of scope for v1:** a hostile insider on the host, and nation-state
adversaries. This is a single-user local deployment.

## Consent

**Recording consent is the user's legal responsibility, and the system is built to
make it easy to honour.**

Consent law varies materially by jurisdiction — one-party consent in much of the US
federal system and many states; all-party consent in California, Illinois,
Pennsylvania, Washington, and others; and broadly stricter regimes under GDPR. This
project does not attempt to determine what applies to a given meeting. It provides
the mechanics for recording that a consent decision was made.

**Enforced in the data model:** `Speaker.consent` is a required `ConsentRecord`,
not an optional flag. A voiceprint cannot be enrolled without one. The record stores:

```
ConsentRecord
├── granted_at: datetime
├── method: str          "verbal_on_recording" | "written" | "meeting_policy"
├── scope: ConsentScope   recording_only | recording_and_voiceprint
├── evidence_span: TranscriptSpan | None
└── revoked_at: datetime | None
```

`scope` separates two distinct permissions. Agreeing to be recorded is not agreeing
to have a persistent biometric identifier stored. The system treats them separately
and defaults to the narrower one.

**Revocation** must be a real path, not a policy statement. Revoking consent:
1. Deletes the voiceprint and all embeddings.
2. Reverts that speaker's turns to anonymous labels across all meetings.
3. Optionally purges audio segments where they are the primary speaker.
4. Leaves a tombstone record so the deletion itself is auditable.

## Data handling

### Audio
- Never sent to a third party. Diarization runs locally; that is a large part of
  the reason for accepting pyannote's heavier local dependency footprint.
- Staged under `MEDIA_ROOT` with `0700` permissions.
- Exported to the user's own Drive, which is the durable copy.
- Local staging copies are prunable after export is confirmed.

### Voiceprints
- **Never leave local infrastructure.** Not exported to Drive, not sent to any API.
- Stored as embeddings, not audio — reconstruction is impractical, though embeddings
  are still biometric data and treated as such.
- Deleted immediately and irreversibly on consent revocation.

### Transcripts
- Sent to the LLM provider for enrichment. This is unavoidable for the product to
  function and must be surfaced honestly to the user.
- Redaction hooks run before transmission — a configurable pattern list for
  credentials, keys, and account numbers, applied to prompt payloads.
- Never logged at INFO. Debug-level transcript logging is off by default and gated
  behind an explicit `APP_ENV=development` check.

### OAuth tokens
*Implemented — `services/google_auth.py`.*
- Refresh tokens stored with `0600` permissions in a `0700` directory outside the
  repository tree, written via a private temp file and `os.replace` so a crash cannot
  leave a truncated token and the secret is never briefly world-readable.
- PKCE (S256) on every authorization, and a single-use `state` parameter that expires
  after 10 minutes — without it, an attacker-supplied callback can redirect the user's
  exports into an attacker-controlled Drive.
- Narrowest workable scope: `drive.file` — access limited to files this app created —
  rather than `drive` (full account access). The app cannot read the user's other
  Drive content, which is both correct and a meaningful blast-radius reduction.
- Revocable from the app and from the Google account security page.

## Secrets

- All credentials via environment variables; `.env` is gitignored.
- `credentials.json`, `token.json`, `*.pem` are gitignored explicitly.
- No secret is ever a default value in `config.py`. Missing required secrets fail
  loudly at startup rather than silently falling back.
- Stub services require no credentials, so development and CI never need real ones.

## Drive sharing posture

Files are created private to the user by default. The app never sets
`anyoneWithLink` permissions. If a user wants to share a summary, they share it
themselves through Drive's own UI, where the sharing consequences are visible.

Meeting folders carry a `README.md` stating that the folder contains recordings of
other people and should not be shared without their agreement — the warning is
placed where someone is actually about to make the mistake.

## Retention

Default posture, configurable:

| Asset | Default retention | Rationale |
|-------|-------------------|-----------|
| Raw audio | 12 months | Long enough to re-process with improved models; short enough to bound exposure |
| Transcripts | Indefinite | The primary long-term value; far lower sensitivity than audio |
| Voiceprints | Until consent revoked | Enrollment is a one-time cost worth preserving |
| Derived artifacts | Indefinite | Cheap to keep, expensive to regenerate |
| Vector index | Rebuildable | Pure derived data |

Retention is not implemented in Phase 0. The policy is settled here first because
building the pipeline without knowing the answer produces a system where deletion
is impossible to retrofit.

## Logging

- Structured logs via structlog.
- Transcript content, speaker names, and audio paths are never logged at INFO or above.
- Meeting ids (content hashes) are safe to log; titles are not, since titles routinely
  contain names and topics.
- LLM prompt logging is off by default.

## Known gaps

Honest accounting of what is not yet handled:

1. **No encryption at rest** beyond filesystem permissions. Acceptable for a
   single-user local deployment on an encrypted disk; not acceptable if this ever
   becomes multi-user or hosted.
2. **No audit log** of who accessed which meeting. Single-user, so there is one
   answer — but this must exist before any team feature.
3. **Redaction is pattern-based** and will miss things. It reduces accidental
   credential leakage; it is not a guarantee.
4. **Third-party participants have no interface.** They cannot see what was recorded
   about them or request deletion without going through the user. This is the
   largest ethical gap in the design and should be revisited before any sharing feature.
