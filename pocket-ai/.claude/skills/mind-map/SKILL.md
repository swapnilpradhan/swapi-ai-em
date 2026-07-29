---
name: mind-map
description: Generate a Mermaid mind map showing how a meeting discussion actually branched — branch points, depth, dead ends, and tangents — with every node citing transcript spans. Use this skill whenever the user mentions mind maps, concept maps, visual maps of a discussion, diagramming a meeting, or wants to see the shape or flow of a conversation rather than a linear summary. Also use it when a generated map came out flat, generic, or indistinguishable from a topic list.
---

# Mind maps

Read [`docs/capabilities/04-mind-maps.md`](../../../docs/capabilities/04-mind-maps.md).

## The test this has to pass

**If the map could have been produced from the summary alone, it has failed.**

A topic list with boxes around it is not a mind map. The value here is *spatial recall* —
six months later, "where did the security concern come up" is answered by looking at the
shape rather than reading. That only works if the shape carries information.

What the shape must encode:

- **Branch points** — where one thread split into several
- **Depth** — a topic explored three levels deep looks different from one mentioned once
- **Dead ends** — raised and dropped, visible as a bare leaf
- **Convergence** — separate threads resolving into one decision
- **Proportion** — a tangent that ate a third of the meeting should look large

That last one matters more than it seems. A meeting that rambled should produce a
visibly rambling map. Imposing tidy structure on a disorganized discussion is a lie that
makes the map useless for recall — the user remembers the mess, and the map does not
match their memory.

## Node model

```python
MindMapNode
├── label: str            2-6 words — this is a map, not prose
├── node_type: NodeType   topic | decision | question | tangent
├── spans: list[TranscriptSpan]
└── children: list[MindMapNode]
```

| Type | Meaning | Rendering |
|------|---------|-----------|
| `topic` | Subject of discussion | rounded box |
| `decision` | Something settled | double-bordered |
| `question` | Open, unresolved | `?` prefix |
| `tangent` | Off-thread | dashed |

## Constraints, and why

- **Depth ≤ 4.** Deeper is unreadable, and usually signals over-decomposition rather
  than genuinely deep discussion.
- **Breadth ≤ 7 per node.** Beyond that, group or promote.
- **Labels 2–6 words.** A sentence in a node means the map is being used as prose, which
  defeats the point of a spatial representation.
- **Every node cites spans** (ADR-0004). Uncited nodes are removed.

## Generation

```
1. Identify discussion threads from the attributed transcript (fast tier)
2. Determine parent/child from topical and temporal adjacency
3. Classify node types
4. Prune: drop nodes with < 30s of discussion unless they are decisions
5. Validate spans; drop uncited nodes
6. Render Mermaid; pick layout by width
```

**Step 4 is what makes the map readable.** Without pruning, every passing mention becomes
a node and the result is noise. Decisions are exempt — a decision made in ten seconds
still matters.

## Rendering

Mermaid, always. Text means diffable in git, embeddable in Markdown, hand-editable, and
it renders natively in GitHub, Notion, and Obsidian. A PNG is a dead end — the user
cannot correct it, and neither can we.

Use `mindmap` layout by default; fall back to `graph TD` past roughly 6 top-level
branches, where `mindmap` layout degrades.

Verify the output actually parses. A Mermaid syntax error renders as a raw code block in
the user's Drive folder, which looks broken rather than degraded — particularly easy to
hit with parentheses and quotes in labels.

## Checklist

- [ ] Structure reflects discussion flow, not summary headings
- [ ] Decisions and open questions visually distinct
- [ ] Long tangents appear proportionally large
- [ ] Mermaid renders without syntax errors in GitHub
- [ ] Every node carries valid spans
- [ ] Depth ≤ 4, breadth ≤ 7
- [ ] A rambling meeting produces a rambling map
