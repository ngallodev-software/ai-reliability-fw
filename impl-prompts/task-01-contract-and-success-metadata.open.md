Goal

Verify and minimally patch the `ai-reliability-fw` execution contract needed by `security-ai-eval-lab`.

Repo And Branch Ownership

- Repo: `ai-reliability-fw`
- Branch: `task/t01-contract-alignment`
- You are not alone in the codebase. Preserve existing local changes and adapt to them. Do not revert work from other agents or the user.

Write Scope

- `src/engine/phase_executor.py`
- Add or update one narrow test file only if required to prove the contract

Read Context

- `impl-prompts/guardrails-security-eval-integration.md`
- `src/engine/phase_executor.py`
- `src/engine/decision_engine.py`
- `src/db/repository.py`

Required Changes

- Inspect the current `PhaseExecutor.execute()` success payload before editing anything.
- Keep the current control flow and retry/escalation semantics intact.
- Ensure the success return is backward-safe and includes:
  - `status`
  - `artifact`
  - `call_id`
  - `provider`
  - `model`
  - `latency_ms`
  - `input_tokens`
  - `output_tokens`
  - `token_cost_usd`
- If the current implementation already satisfies that contract, make no code change and return a verification-only result.
- If a code change is required, keep it minimal and local to the executor success path.

Guardrails

- You must follow rules in `impl-prompts/guardrails-security-eval-integration.md`.
- Do not redesign `PhaseExecutor`.
- Do not add new persistence entities, config systems, or abstractions.
- Do not hard-code eval-lab-specific logic into framework internals.
- Do not touch migrations unless you can prove a concrete blocker.
- Do not edit outside the listed write scope.

Required Validation

- Confirm the success payload keys and names in code.
- If there is a narrow test for executor behavior, run it.
- If no relevant test exists and a code change was made, add the smallest test that proves the success payload shape.

Response Contract

- Summarize whether you changed code or only verified current behavior.
- List all changed file paths, or `none`.
- End with this exact footer:

```text
TASK_ID: t01
STATUS: <completed|blocked>
TOKENS_USED: <number>
ELAPSED_SECONDS: <number>
ERRORS_ENCOUNTERED: <none or brief list>
TESTS_RUN: <command summary or none>
CHANGED_FILES: <comma-separated paths or none>
SUMMARY: <one short paragraph>
```
