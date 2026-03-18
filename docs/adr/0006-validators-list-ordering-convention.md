# ADR-0006: validators[0] Is Always the Input Validator

## Status

Accepted

## Date

2026-03-16

## Context

`PhaseExecutor` needs to distinguish pre-call input validation (run once, before any LLM call) from post-call output validation (run after each LLM call). A separate parameter for each would complicate the constructor.

## Decision

By convention, `validators[0]` is always the pre-call input validator. `validators[1:]` are post-call validators, run against `response_raw` after each LLM call. This ordering is not enforced by the type system.

## Consequences

- Constructor signature stays simple: one `validators: Sequence[BaseValidator]` list.
- Any caller that passes validators in the wrong order silently skips pre-call validation — there is no runtime guard.
- Future work could enforce this via a typed wrapper (e.g. `InputValidator` subclass check).
