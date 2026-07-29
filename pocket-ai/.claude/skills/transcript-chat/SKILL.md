---
name: transcript-chat
description: Answer natural-language questions over one meeting, a meeting series, or the whole transcript corpus using hybrid retrieval (speaker and date filters plus semantic search), always citing the meeting and span. Use this skill whenever the user wants to ask questions of their meetings, search their transcripts, recall what was said or decided, find when a topic first came up, or track what someone committed to. Also use it when working on chunking, embedding, indexing, or retrieval quality for the transcript corpus.
---

# Chat with transcripts

Read [`docs/capabilities/06-transcript-chat.md`](../../../docs/capabilities/06-transcript-chat.md).

## The one rule that makes this valuable

**Refuse when the corpus does not support an answer.**

"I don't find any discussion of that in your meetings" is a correct and useful response.
The entire value proposition is that these answers come from *your* meetings — one
confident answer drawn from general knowledge destroys that, permanently, because the
user now has to verify everything.

This is harder than it sounds, because a good model can always produce a plausible
answer about Kafka migrations. The instruction has to be explicit and the retrieval
results have to be the only context.

Also distinguish **"not discussed"** from **"not retrieved"**. If filters were narrow,
say so and offer to widen. Those are very different answers and conflating them sends
the user away believing something never came up.

## Retrieval is hybrid, not semantic

This is the most important implementation decision. "What did Priya commit to in Q2
planning" is not one query. It is:

- a metadata filter — `speakers contains Priya`, `series = Q2 planning`
- plus a semantic search — `commitment`

Run as pure vector similarity, it returns chunks that are *about* commitments by anyone,
confidently and wrongly. The speaker filter has to be a real filter on real metadata.

```
1. Parse question → filters (speaker, date range, series) + semantic query
2. Apply metadata filters
3. Semantic search within the filtered set (k ≈ 12)
4. Rerank by relevance and recency
5. Answer from retrieved chunks only, with citations
```

Date expressions ("last quarter", "since the offsite") resolve to filters, not search terms.

## Chunking makes or breaks this

```python
Chunk
├── text: str                  ~400 tokens
├── meeting_id / series_id / occurred_at
├── speakers: list[str]        first-class filter field, not just text
├── segment_range: (int, int)  for span reconstruction
└── preceding_context: str     ~100 tokens of the prior chunk
```

- **Split on speaker-turn boundaries, never mid-turn.** A chunk cutting through a
  sentence loses the claim it contained, and that claim is unrecoverable at query time.
- **Carry preceding context.** A chunk starting "yeah, I agree with that" is meaningless
  alone and will retrieve for the wrong queries.
- **Speaker metadata is structured**, not embedded in the text and hoped for.

## Scope is explicit

| Scope | Retrieval |
|-------|-----------|
| `meeting` | Full transcript if it fits, else chunked |
| `series` | Filtered to `series_id`, time-ordered |
| `corpus` | Full index, hybrid search |

Never infer scope. Inferring wrongly produces answers that are right about the wrong
meeting — a failure the user has almost no way to notice.

## Answering rules

1. **Cite every claim** — meeting title, date, span. Clickable through to the moment.
2. **Refuse rather than reach outside the corpus.**
3. **Surface conflicts.** If two meetings contradict, present both with dates. Do not
   silently prefer the more recent one.
4. **Be time-aware.** "What did we decide" should prefer the latest decision but note
   changes: "decided X in May, revised to Y in July" is the real answer, and it is
   usually the thing the user actually needed to know.

## Practical

- Indexing is incremental. A new meeting indexes alone; never re-embed the corpus except
  on explicit rebuild.
- Target < 5s for corpus-scope queries over 500 meetings.
- Reranking is probably worth the latency at corpus scope, probably not at meeting scope.

## Checklist

- [ ] Speaker-filtered questions return only that speaker's content
- [ ] Answers cite correct meeting and span ≥ 90% of the time
- [ ] Unsupported questions are refused, not answered from general knowledge
- [ ] "Not discussed" vs "not retrieved" are distinguished
- [ ] Contradictions surfaced, not silently resolved
- [ ] Chunks never split mid-turn
- [ ] "Yeah, exactly" chunks resolvable via preceding context
- [ ] Incremental indexing needs no full re-embed
