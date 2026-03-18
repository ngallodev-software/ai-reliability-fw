# ADR-0005: ON CONFLICT DO NOTHING for Idempotent Inserts

## Status

Accepted

## Date

2026-03-16

## Context

Network failures, process restarts, or test reruns can cause the same record to be inserted more than once. Raising a unique-constraint error in those cases would require callers to handle deduplication logic.

## Decision

All `persist_*` methods in `ReliabilityRepository` use `INSERT … ON CONFLICT DO NOTHING` on the primary key. `update_run_status` includes an idempotency guard that skips the update if the status is already set.

## Consequences

- Every write operation is safe to call multiple times with the same arguments.
- Callers do not need to check existence before inserting.
- Silent deduplication means a bug that sends duplicate data will not surface as an error — monitoring must catch unexpected call counts another way.
