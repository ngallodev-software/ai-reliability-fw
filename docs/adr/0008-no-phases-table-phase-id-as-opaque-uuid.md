# ADR-0008: No phases Table — phase_id Is a Caller-Supplied Opaque UUID

## Status

Accepted

## Date

2026-03-16

## Context

Multi-phase workflows need a way to group LLM calls and escalations by phase. Adding a `phases` table would require callers to pre-register phases and manage another FK relationship.

## Decision

`phase_id` is a plain `UUID` column on `llm_calls` and `escalation_records` with no foreign key constraint and no `phases` table. The caller generates and owns `phase_id` values.

## Consequences

- Schema stays simple; no extra pre-registration step for callers.
- Phase-level metadata (name, ordering, status) cannot be stored or queried — referential integrity is not enforced.
- If phase-level querying becomes important, a `phases` table can be added in a future migration without breaking existing rows.
