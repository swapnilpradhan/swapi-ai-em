# ADR-0001: Record architecture decisions

**Status:** Accepted · **Date:** 2026-07-29

## Context

This project spans four phases and a wide capability surface — storage, audio ML,
retrieval, document generation, coaching. Decisions made in Phase 1 constrain
Phase 4 in ways that are not obvious at the time. Six months later the reasoning
behind a choice is gone, and the choice gets either cargo-culted or reversed
without understanding what it was protecting.

## Decision

Record every architecturally significant decision as a numbered ADR in `docs/adr/`.

A decision is architecturally significant if reversing it would require changing
more than one service, would alter the data model, or has legal/privacy
consequences.

Format: Context → Decision → Consequences → Alternatives considered. Short. An ADR
that takes twenty minutes to write will not get written.

ADRs are immutable once accepted. A changed decision gets a new ADR that supersedes
the old one; the old one stays, marked superseded. The history of what we believed
and why is the point.

## Consequences

- Some friction on every significant decision — intended.
- New contributors (and future Claude sessions) can read the reasoning rather than
  reverse-engineering it from code.
- Risk: ADRs drift from reality if not maintained. Mitigated by keeping them short
  and by `CLAUDE.md` pointing at them for load-bearing decisions.

## Alternatives considered

**Comments in code.** Too local. Cross-cutting decisions have no natural home, and
the reasoning gets deleted with the code it annotated.

**A wiki.** Separated from the code, so it drifts faster and is not reviewed in PRs.

**Nothing.** The default, and the reason most codebases accumulate decisions nobody
can explain.
