# C6 — Chat with transcripts

**Phase:** 3 · **Skill:** `.claude/skills/transcript-chat` · **Service:** `backend/app/services/retrieval.py`

## Intent

Ask questions of your meeting history in natural language and get answers you can
verify. "What did we decide about the Kafka migration?" "What has Priya committed to
this quarter?" "When did the security concern first come up?"

This is where the corpus stops being an archive and starts being an asset.

## Scopes

| Scope | Use | Retrieval |
|-------|-----|-----------|
| `meeting` | Deep dive on one conversation | Full transcript in context if it fits, else chunked |
| `series` | "How has this project evolved?" | Chunks filtered to `series_id`, time-ordered |
| `corpus` | "Have we ever discussed X?" | Full index, hybrid search |

Scope is explicit, not inferred. Inferring it wrongly produces answers that are right
about the wrong meeting — a failure that is hard to notice.

## Chunking

The chunking strategy is what makes this work or fail. Naive fixed-size chunks destroy
the properties that make transcripts queryable.

```python
Chunk
├── text: str                  ~400 tokens, split on speaker-turn boundaries
├── meeting_id: str
├── series_id: str | None
├── occurred_at: datetime
├── speakers: list[str]        every speaker appearing in the chunk
├── segment_range: (int, int)  for span reconstruction
└── preceding_context: str     ~100 tokens of the prior chunk
```

Rules:
- **Split on turn boundaries, never mid-turn.** A chunk cutting through a sentence
  loses the claim it contained.
- **Carry preceding context** so a chunk starting with "yeah, I agree with that" is
  resolvable.
- **Speaker metadata is a first-class filter field**, not just text. This is the key
  design decision — see below.

## Hybrid retrieval

"What did Priya commit to in Q2 planning" is not one query. It is a metadata filter
(`speakers contains Priya`, `series = Q2 planning`) plus a semantic search
(`commitment`). Running it as pure vector similarity returns chunks that are
*about* commitments by whoever, which is the wrong answer delivered confidently.

```
1. Parse the question → filters (speaker, date range, series) + semantic query
2. Apply metadata filters
3. Semantic search within the filtered set (top-k, k≈12)
4. Rerank by relevance and recency
5. Answer from retrieved chunks only, with citations
```

Date expressions ("last quarter", "since the offsite") resolve to filters, not to
search terms.

## Answering rules

1. **Cite every claim.** Meeting title, date, and span. Answers are clickable through
   to the moment.
2. **Refuse when the corpus does not support an answer.** "I don't find any discussion
   of that in your meetings" is a correct and useful response. Never fill the gap with
   general knowledge — the entire value is that this is grounded in *your* meetings,
   and a single confident answer from outside the corpus destroys that.
3. **Distinguish "not discussed" from "not retrieved".** If filters were restrictive,
   say so and offer to widen.
4. **Surface conflicts.** If two meetings contradict each other, present both with
   dates rather than picking the more recent.
5. **Time-aware.** "What did we decide" should prefer the most recent decision but
   note if it changed — "decided X in May, revised to Y in July" is the real answer.

## Interface

```python
class RetrievalService(Protocol):
    async def index(self, meeting: Meeting) -> None: ...
    async def search(self, query: str, *, scope: Scope, filters: Filters) -> list[Chunk]: ...


class ChatService(Protocol):
    async def ask(self, question: str, *, scope: Scope, history: list[Turn]) -> CitedAnswer: ...
```

Indexing is incremental. A new meeting indexes in isolation; the whole corpus is never
re-embedded except on an explicit rebuild.

## Acceptance criteria

- [ ] Speaker-filtered questions return only that speaker's content
- [ ] Answers cite the correct meeting and span ≥ 90% of the time
- [ ] Questions with no corpus support are refused, not answered from general knowledge
- [ ] Contradictions across meetings are surfaced, not resolved silently
- [ ] Date-range questions resolve to filters
- [ ] Chunks never split mid-turn
- [ ] "Yeah, exactly" chunks are resolvable via preceding context
- [ ] Incremental indexing does not require full re-embedding
- [ ] Corpus-scope queries over 500 meetings return in < 5s

## Open questions

- Reranker: worth the latency? Probably yes at corpus scale, likely not at meeting scope.
- Conversation memory across turns — how much history to carry before it degrades retrieval.
- Whether to index summaries alongside raw transcript. Summaries retrieve better for
  "what happened" questions; raw transcript is better for "who said what".
