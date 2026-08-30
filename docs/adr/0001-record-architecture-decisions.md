# ADR-0001: Record architecture decisions

- Status: Accepted
- Date: 2026-08-30

## Context

This is a solo project expected to run for a long time with long gaps between
sessions. Decisions and their rationale need to survive so they are not
re-litigated or silently reverted.

## Decision

Record every architecturally significant decision as an ADR in `docs/adr/`,
following the process in `docs/adr/README.md`. `docs/development-plan.md` holds
the roadmap; ADRs hold the "why" behind specific choices.

## Consequences

- A small per-decision writing cost.
- New contributors (including future me, and AI assistants) can reconstruct
  intent from the repo alone.
- Superseding rather than editing keeps the history honest.

## Alternatives considered

- **Rationale in commit messages / PR descriptions only** — hard to find later,
  not indexed.
- **A single "decisions" doc** — grows unwieldy and invites editing history away.
