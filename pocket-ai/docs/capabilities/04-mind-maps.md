# C4 — Mind maps

**Phase:** 2 · **Skill:** `.claude/skills/mind-map` · **Service:** `backend/app/services/insights.py`

## Intent

Show how the discussion actually *branched*. Not a topic list with a box around it —
a structural picture of where the conversation forked, what got resolved, what got
parked, and which tangent quietly consumed twenty minutes.

The value is spatial recall. Six months later, "where in the discussion did the
security concern come up" is answered by looking at the shape, not by reading.

## What makes this different from a topic list

A topic list is flat and derivable from headings. A mind map is useful only if it
captures *relationships*:

- **Branch points** — where one thread split into several.
- **Depth** — a topic explored three levels deep looks different from one mentioned once.
- **Dead ends** — a branch raised and dropped without resolution is visible as a leaf.
- **Convergence** — separate threads that resolved into one decision.
- **Proportion** — a tangent that consumed a third of the meeting should look large.

If the generated map could be produced from the summary alone, it has failed.

## Node model

```python
MindMapNode
├── label: str            short — 2-6 words; this is a map, not prose
├── node_type: NodeType   topic | decision | question | tangent
├── spans: list[TranscriptSpan]
└── children: list[MindMapNode]
```

`node_type` drives rendering:

| Type | Meaning | Mermaid shape |
|------|---------|---------------|
| `topic` | Subject of discussion | rounded box |
| `decision` | Something settled | double-bordered |
| `question` | Open, unresolved | box with `?` prefix |
| `tangent` | Off-thread, notable if long | dashed |

## Rendering

Mermaid, always. Text-based means: diffable in git, embeddable in Markdown,
hand-editable, renders natively in GitHub, Notion, Obsidian, and most modern viewers.
A PNG would be a dead end.

```mermaid
mindmap
  root((Platform Architecture Review))
    Kafka migration
      Timeline risk
        ::icon(fa fa-question) Capacity unknown
      Decision: defer to Q4
    Observability gaps
      Tracing coverage
      Cost of retention
    (Tangent: hiring)
```

Fall back to `graph TD` when the map is wide enough that `mindmap` layout degrades —
roughly beyond 6 top-level branches.

## Constraints

- **Max depth 4.** Deeper is unreadable and usually reflects over-decomposition.
- **Max 7 children per node.** Beyond that, group or promote.
- **Labels 2–6 words.** A sentence in a node means the map is being used as prose.
- **Every node cites spans.** Per ADR-0004; a node that cannot cite is removed.
- **Root is the meeting title.**

## Generation

```
1. Identify discussion threads from the attributed transcript (fast tier)
2. Determine parent/child relationships from topical and temporal adjacency
3. Classify each node's type
4. Prune: drop nodes with < 30s of discussion unless they are decisions
5. Validate spans; drop uncited nodes
6. Render Mermaid; select layout by width
```

Step 4 matters. Without pruning, every passing mention becomes a node and the map
becomes noise.

## Acceptance criteria

- [ ] Map structure reflects actual discussion flow, not summary headings
- [ ] Decisions and open questions are visually distinct
- [ ] Long tangents appear proportionally
- [ ] Mermaid renders without syntax errors in GitHub
- [ ] Every node carries valid spans
- [ ] Depth ≤ 4, breadth ≤ 7 per node
- [ ] A rambling meeting produces a visibly rambling map — the map should not impose
      false structure on a disorganized discussion
