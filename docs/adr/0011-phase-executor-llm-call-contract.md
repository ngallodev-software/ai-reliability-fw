# ADR-0011: PhaseExecutor Owns the LLM Call Contract and Success Metadata

## Status

Accepted

## Date

2026-03-17

## Context

`PhaseExecutor` is the framework-owned boundary between workflow orchestration and the pluggable LLM client. The executor already persists call metadata and returns a success payload that other consumers rely on. During security-eval integration review, the code and tests made it clear that this boundary needs to stay explicit:

- the LLM client contract is `call(prompt, model)`
- the executor is responsible for supplying the model argument
- the success payload must expose the framework-owned metadata needed by downstream integrations without widening the API further

Leaving this implicit creates two failure modes: runtime breakage when a client expects `(prompt, model)`, and accidental drift in the success payload shape.

## Decision

Keep the LLM invocation and success payload contract explicit in `PhaseExecutor.execute()`:

- `PhaseExecutor` calls `llm_client.call(str(input_artifact), model)`
- the executor remains responsible for choosing and propagating the model value
- the success payload remains backward-safe and includes `status`, `artifact`, `call_id`, `provider`, `model`, `latency_ms`, `input_tokens`, `output_tokens`, and `token_cost_usd`

This contract is validated with focused executor tests rather than a broader orchestration redesign.

## Consequences

- The framework boundary is clear: LLM clients implement a stable two-argument call contract, and integrations consume a stable success payload.
- Downstream integrations can rely on the returned metadata without reaching into persistence internals.
- The current model selection remains intentionally simple and local to the executor; making model choice configurable is a separate decision.
- Any future change to the success payload or LLM client signature now requires an explicit ADR-worthy decision instead of incidental drift.
