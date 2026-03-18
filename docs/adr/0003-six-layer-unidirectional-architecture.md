# ADR-0003: Six-Layer Unidirectional Architecture

## Status

Accepted

## Date

2026-03-16

## Context

Without clear layering, LLM orchestration code tends to mix SQL, business logic, and validation in the same functions. This makes the system hard to test and reason about.

## Decision

Enforce a strict six-layer stack where dependencies only flow downward:

```
entry points (demo/, tests/)
    ↓
engine layer (PhaseExecutor, decision_engine)
    ↓
validators layer (BaseValidator and subclasses)
    ↓
db layer (ReliabilityRepository, session)
    ↓
core layer (models.py — ORM models + enums)
    ↓
PostgreSQL
```

No layer may import from a layer above it.

## Consequences

- Each layer is independently testable with fakes at the boundary above it.
- Adding a new validator or DB method does not require touching the engine.
- Enforced by convention only — no tooling prevents upward imports today.
