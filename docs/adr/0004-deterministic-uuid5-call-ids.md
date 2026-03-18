# ADR-0004: Deterministic UUID5 for LLM Call IDs

## Status

Accepted

## Date

2026-03-16

## Context

LLM calls can be retried or replayed (e.g. after a crash mid-loop). If each retry generates a new random ID, duplicate `llm_calls` rows accumulate and replay is not idempotent.

## Decision

Compute `call_id` as `uuid5(NAMESPACE_URL, "{run_id}:{phase_id}:{prompt_id}:{attempt_num}")`. The same inputs always produce the same ID.

## Consequences

- Replaying a run with the same parameters is safe — the duplicate insert is silently ignored (see ADR-0005).
- The ID encodes the logical position of the call, making it inspectable without querying.
- Two different calls that share all four inputs would collide — callers must ensure `attempt_num` increments correctly and `run_id` is unique per run.
