# ADR-0009: Manual Constructor Dependency Injection

## Status

Accepted

## Date

2026-03-16

## Context

The framework needs to swap out the LLM client, repository, and validators between production use and tests. A DI framework adds dependencies and indirection.

## Decision

Dependencies are injected explicitly via constructors. `PhaseExecutor(repository, llm_client, validators)` and `ReliabilityRepository(session)` take all dependencies as arguments. No DI framework is used.

## Consequences

- Every dependency is visible at the call site — easy to trace and reason about.
- Tests swap in `FakeLLMClient`, in-memory session fakes, or stub validators without any framework configuration.
- Wiring is the caller's responsibility; there is no automatic lifecycle management or scoping.
