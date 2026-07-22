# ADR 0001 — Record architecture decisions

## Status
Accepted

## Context
This is a long-lived, evidence-driven system that will evolve as markets and the
trader's own performance data change. Decisions made now (schema shape, module
boundaries, risk-rule handling) will be revisited. We need a durable, low-friction
record of *why* each significant choice was made so future changes are informed
rather than accidental.

## Decision
We keep lightweight Architecture Decision Records in `docs/adr/`, one file per
decision, numbered sequentially. Each records context, the decision, and its
consequences. Superseded ADRs are marked, not deleted.

## Consequences
- The reasoning behind the architecture is auditable — consistent with the
  system's own "every decision should be explainable" principle.
- Minimal overhead: a new ADR is a short markdown file.
