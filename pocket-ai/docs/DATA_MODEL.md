# Data model

The Pydantic definitions in `backend/app/models/` are authoritative. This document
explains the reasoning — why the entities are cut this way and what each one is
protecting against.

## Core entities

### Meeting

The unit of everything. Created at ingest, enriched over time.

```
Meeting
├── id: str                    stable, derived from audio content hash
├── title: str
├── occurred_at: datetime
├── duration_seconds: float
├── series_id: str | None      links recurring meetings
├── source: MeetingSource      pocket_ai | manual_upload
├── audio: AudioRef
├── transcript: Transcript
├── participants: list[Participant]
└── status: ProcessingStatus   per-stage state, not a single flag
```

`status` is a per-stage map rather than one enum because stages fail independently.
"Diarization failed but summarization succeeded" is a real and useful state.

### AudioRef

A pointer, never bytes.

```
AudioRef
├── content_hash: str          sha256 — the idempotency anchor for the whole pipeline
├── local_path: Path | None    staging only; may be pruned after export
├── drive_file_id: str | None  the durable location
├── duration_seconds: float
├── sample_rate: int
└── quality: AudioQuality      snr_db, clipping_ratio, silence_ratio
```

`quality` is captured at ingest and gates diarization. Diarizing audio that was
never going to work wastes minutes of compute and produces confidently wrong turns.

### Transcript and TranscriptSpan

```
Transcript
├── segments: list[TranscriptSegment]
└── source: TranscriptSource   pocket_ai_raw | rediarized | manually_corrected

TranscriptSegment
├── index: int
├── start_ms: int
├── end_ms: int
├── text: str
└── speaker_id: str | None     None until identification runs

TranscriptSpan                 ← the load-bearing type
├── meeting_id: str
├── segment_start: int
├── segment_end: int
└── quote: str                 verbatim, for display and validation
```

**`TranscriptSpan` is what makes the whole system trustworthy.** Every generated
claim — a summary bullet, an action item, a coaching observation — carries one or
more spans. Validation checks that the quote actually appears in the referenced
segments. A claim that cannot produce a valid span is dropped before it reaches
the user. This is the single most important constraint in the codebase.

`quote` is stored redundantly (it is derivable from the segment range) so that
citations survive a re-diarization that renumbers segments, and so validation does
not require loading the full transcript.

### Speaker and Voiceprint

```
Speaker
├── id: str
├── display_name: str
├── aliases: list[str]
├── relationship: str | None    "direct report", "skip", "peer", "external"
├── consent: ConsentRecord      granted_at, method, revocable
└── voiceprint: Voiceprint | None

Voiceprint
├── embeddings: list[list[float]]   multiple samples improve robustness
├── enrolled_at: datetime
├── sample_count: int
└── library_version: int            bumped on change; part of the identification cache key
```

Consent is a required field on `Speaker`, not an optional flag elsewhere. Making it
structurally impossible to enroll a voiceprint without a consent record is the point.

`library_version` in the identification idempotency key means adding a new speaker
automatically re-runs identification across affected meetings — a person who was
"Speaker 3" in ten past meetings becomes named retroactively.

### MeetingInsights

Partial by design.

```
MeetingInsights
├── meeting_id: str
├── prompt_version: str
├── one_line: Cited[str] | None
├── executive_summary: Cited[str] | None
├── full_brief: Cited[str] | None
├── decisions: list[Cited[Decision]]
├── action_items: list[ActionItem]
├── risks: list[Cited[Risk]]
├── open_questions: list[Cited[Question]]
├── disagreements: list[Cited[Disagreement]]
├── mind_map: MindMap | None
└── section_status: dict[str, SectionStatus]
```

`Cited[T]` wraps a value with its supporting spans. Making citation part of the type
rather than a convention means an uncited claim is a type error, not a code-review catch.

`disagreements` is called out separately from `decisions` deliberately. Where a room
did *not* converge is often the most valuable thing in a meeting, and generic
summarizers smooth it away into false consensus.

### ActionItem

```
ActionItem
├── id: str
├── description: str
├── owner_speaker_id: str | None
├── owner_raw: str              what was actually said: "you", "the platform team"
├── due: DueDate | None         parsed + raw ("by Friday", "end of quarter")
├── confidence: float
├── commitment_type: CommitmentType   firm | soft | hypothetical | assigned
├── spans: list[TranscriptSpan]
├── confirmed_by_user: bool
└── status: ActionStatus
```

`commitment_type` is the field that makes this useful rather than noisy. "I'll send
it Friday" (firm), "I could take a look" (soft), and "someone should probably
review this" (hypothetical) are different objects. Flattening them into one list
produces a to-do list nobody trusts.

`owner_raw` preserves the ambiguity of real speech. "You should handle that" needs
the raw text to be resolvable later — collapsing it to a guessed speaker id loses
the information needed to correct the guess.

### MindMap

```
MindMap
├── root: MindMapNode
└── rendered_mermaid: str

MindMapNode
├── label: str
├── spans: list[TranscriptSpan]
├── node_type: NodeType         topic | decision | question | tangent
└── children: list[MindMapNode]
```

Mermaid because it is text: diffable, embeddable in Markdown, editable by hand,
renders natively in most modern viewers. A PNG would be a dead end.

### CoachingAssessment

```
CoachingAssessment
├── id: str
├── assessed_at: datetime
├── track: CoachingTrack        written | spoken | thought_leadership | thought_development
├── source_refs: list[TranscriptSpan | DocumentRef]
├── scores: dict[str, RubricScore]   dimension -> score + evidence
├── observations: list[Cited[str]]
├── drills: list[Drill]
└── delta_from_previous: dict[str, float] | None
```

Scores are per-dimension with attached evidence, never a single opaque number. The
value is in "you hedge recommendations under challenge" plus the clip, not in "7/10".

### ExportManifest

```
ExportManifest
├── meeting_id: str
├── entries: list[ManifestEntry]   artifact_kind, drive_file_id, content_hash, exported_at
└── last_full_sync: datetime | None
```

Written to Drive alongside the artifacts, not only to the database. If the database
is lost, the manifest in Drive is enough to reconstruct export state — which is what
makes the "Drive survives independently" claim real rather than aspirational.

## Relationships

```
MeetingSeries 1─* Meeting 1─1 AudioRef
                     │
                     ├─1 Transcript 1─* TranscriptSegment
                     ├─* Participant *─1 Speaker 1─0..1 Voiceprint
                     ├─1 MeetingInsights 1─* ActionItem
                     │                   └─0..1 MindMap
                     └─1 ExportManifest 1─* ManifestEntry

Speaker 1─* CoachingAssessment   (the user's own speaker record)
```

## Identity and idempotency

| Entity | Identity | Rationale |
|--------|----------|-----------|
| Meeting | sha256 of audio | Re-uploading the same file is a no-op, not a duplicate |
| Speaker | uuid | Names change; identity should not |
| ActionItem | uuid, stable across re-runs via span match | Re-summarizing must not orphan user edits |
| Insights | `(meeting_id, prompt_version)` | Prompt improvement invalidates cleanly |
| Export entry | `(meeting_id, artifact_kind)` | Updates in place; never `transcript (2).md` |

## Migration posture

Phase 0–1 runs on Pydantic models serialized to JSON on disk — enough for a single
user with a few hundred meetings, and it keeps the schema fluid while the model is
still moving. SQLAlchemy tables and Alembic migrations land in Phase 2, when
cross-meeting queries (corpus chat, coaching trends) make real indexes necessary.
The Pydantic models stay as the API and service-layer contract either way; the ORM
is a persistence detail underneath them.
