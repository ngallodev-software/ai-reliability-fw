# ADR-0007: Decision Engine as a Pure Function

## Status

Accepted

## Date

2026-03-16

## Context

The retry/escalate/complete logic is the core business rule of the framework. If it is entangled with DB writes or LLM calls, it becomes difficult to unit-test exhaustively.

## Decision

`decide(failures, policy, attempt_num)` is a pure function in `src/engine/decision_engine.py`. It takes failure categories, a `RetryPolicy`, and the current attempt number, and returns a `Decision(action, reason)`. It performs no I/O.

## Consequences

- All decision logic is covered by fast, in-process unit tests with no mocking required.
- `PhaseExecutor` is responsible for calling `decide()` and acting on the result — the engine has no knowledge of DB or LLM state.
- Policy changes (new `FailureCategory` handling) are isolated to this one function and its tests.
