# AI Reliability Framework — TODO

## How to use this list

- Tasks marked **[parallel-safe]** have no dependencies on each other and can be delegated to separate agents/models simultaneously.
- Tasks marked **[sequential]** must follow completion of their listed prerequisite(s).
- Delegation suggestions use `>` to indicate which model tier fits the task.
  - `> haiku` — mechanical / boilerplate work, cheap to run
  - `> sonnet` — moderate reasoning, standard implementation
  - `> opus` — design decisions, complex logic, architecture

---

## Phase 1 — Test coverage (no DB required) [parallel-safe]

These can all be delegated and run concurrently. Each targets a different module with no shared state.

### 1a. Unit tests for `decision_engine.py` [parallel-safe]
> sonnet

`decide()` is a pure function — ideal for exhaustive unit tests.

- [ ] `SAFETY_FLAG` always escalates regardless of attempt number
- [ ] `INPUT_VALIDATION_ERROR` always escalates
- [ ] retry fires when attempt < max_attempts and rule exists
- [ ] escalate fires when attempt >= max_attempts
- [ ] complete fires when no failures
- [ ] multiple failure categories — worst-case wins (escalate beats retry)
- [ ] unknown failure category with no policy rule → escalate

File: `tests/test_decision_engine.py`
Run: `python3 -m unittest tests.test_decision_engine`

---

### 1b. Unit tests for validators [parallel-safe]
> haiku

Both validators are stateless and take simple inputs.

**`InputIntegrityValidator`** (`src/validators/input_schema_validator.py`):
- [ ] passes when all required fields present
- [ ] fails with `INPUT_VALIDATION_ERROR` when a required field is missing
- [ ] fails when artifact is not a dict

**`JsonSchemaValidator`** (`src/validators/json_schema_validator.py`):
- [ ] passes when response string is valid JSON matching schema
- [ ] fails with `OUTPUT_SCHEMA_ERROR` (or equivalent) when JSON is invalid
- [ ] fails when JSON is valid but violates schema

File: `tests/test_validators.py`
Run: `python3 -m unittest tests.test_validators`

---

### 1c. Additional `PhaseExecutor` smoke tests [parallel-safe]
> sonnet

Extend `tests/test_phase_executor.py` using the existing `FakeRepository` / `FakeLLMClient` pattern.

- [ ] escalates immediately when `SAFETY_FLAG` failure occurs on first attempt
- [ ] completes on first attempt when all validators pass immediately
- [ ] `persist_llm_call` called once per attempt (verify call count)
- [ ] `update_run_status` final value is `COMPLETED` vs `ESCALATED` per scenario
- [ ] deterministic call ID: same inputs produce same UUID (replay safety)

---

## Phase 2 — LLM client layer [parallel-safe]

### 2a. Anthropic SDK client (`src/llm/anthropic_client.py`) [parallel-safe]
> sonnet
> Depends on: nothing (pure addition)

The current `CLIProvider` is a manual stdin harness. Add a real async client.

- [ ] Implement `AnthropicClient(BaseLLMClient)` using `anthropic` SDK
- [ ] `call(prompt, model)` → returns `{response_raw, latency_ms, provider, model}`
- [ ] Reads API key from env (`ANTHROPIC_API_KEY`)
- [ ] Handles `anthropic.APIError` → raise or return structured error dict
- [ ] Wire into `demo/failure_path_runner.py` as an optional `--provider anthropic` flag

Use skill: `/claude-api` for Anthropic SDK usage patterns.

---

### 2b. OpenAI-compatible client (`src/llm/openai_client.py`) [parallel-safe]
> haiku
> Depends on: nothing

- [ ] Implement `OpenAIClient(BaseLLMClient)` using `openai` async SDK
- [ ] Same return contract as above
- [ ] Reads `OPENAI_API_KEY` from env

---

## Phase 3 — Validator expansion [parallel-safe]

Each validator is independent.

### 3a. Semantic / content validator (`src/validators/content_validator.py`) [parallel-safe]
> sonnet

- [ ] `ContentValidator(BaseValidator)` — checks LLM response for required keywords or patterns (regex or substring list)
- [ ] Returns `OUTPUT_CONTENT_ERROR` failure category on miss
- [ ] Add `OUTPUT_CONTENT_ERROR` to `FailureCategory` enum in `src/core/models.py`
- [ ] Add migration: `alembic revision --autogenerate -m "add output_content_error"`
- [ ] Unit tests in `tests/test_validators.py`

### 3b. Safety / toxicity check stub (`src/validators/safety_validator.py`) [parallel-safe]
> sonnet

- [ ] `SafetyValidator(BaseValidator)` — checks response against a configurable blocklist
- [ ] Returns `SAFETY_FLAG` on match
- [ ] Configurable: accepts `blocked_patterns: list[str]` in constructor
- [ ] Unit tests

---

## Phase 4 — Repository & DB [sequential after Phase 1 passes]

### 4a. Integration test suite (`tests/test_repository.py`) [sequential]
> sonnet
> Depends on: Docker Postgres running (`docker compose up -d db && alembic upgrade head`)

- [ ] `persist_workflow` → row exists in DB
- [ ] `persist_llm_call` idempotency: duplicate insert → no error, no duplicate row
- [ ] `update_run_status` guard: transition from `COMPLETED` → `RUNNING` is a no-op
- [ ] `create_escalation` links correctly to `run_id` and `llm_call_id`

### 4b. Query methods on `ReliabilityRepository` [sequential]
> sonnet
> Depends on: 4a (so tests exist before implementation)

Currently the repository is write-only. Add reads:
- [ ] `get_run(run_id) -> WorkflowRun | None`
- [ ] `get_calls_for_run(run_id) -> list[LLMCall]`
- [ ] `get_escalations_for_run(run_id) -> list[EscalationRecord]`
- [ ] Tests for each

### 4c. Migration: add `attempt_num` index [parallel-safe]
> haiku

- [ ] Add index on `llm_calls.attempt_num` + `llm_calls.run_id` for query performance
- [ ] `alembic revision -m "add_llm_calls_run_attempt_idx"`

---

## Phase 5 — Observability [parallel-safe]

### 5a. Structured logging (`src/observability/logging.py`) [parallel-safe]
> haiku

- [ ] JSON-structured log emitter (stdlib `logging` + `json` formatter)
- [ ] Log on: each validator result, each decision, each DB persist
- [ ] Configurable log level via `LOG_LEVEL` env var

### 5b. Metrics stub (`src/observability/metrics.py`) [parallel-safe]
> sonnet

- [ ] Dataclass `RunMetrics` collecting per-run: attempt count, total latency, final status, failure categories seen
- [ ] `PhaseExecutor.execute()` returns `RunMetrics` alongside final status
- [ ] Update `PhaseExecutorSmokeTests` to assert on returned metrics

---

## Phase 6 — Packaging & CI [sequential after Phase 1-3]

### 6a. `pyproject.toml` [parallel-safe]
> haiku

- [ ] Replace ad-hoc `requirements.txt` with `pyproject.toml` (PEP 517)
- [ ] Define `[project]`, `[project.optional-dependencies]` (dev extras: pytest, etc.)
- [ ] Keep `requirements.txt` as a pinned lockfile generated from pyproject

### 6b. GitHub Actions CI [parallel-safe]
> haiku

- [ ] `.github/workflows/ci.yml`
- [ ] Jobs: lint (`ruff`), type check (`mypy`), unit tests (no DB), integration tests (with Postgres service)
- [ ] Matrix: Python 3.11, 3.12, 3.13

### 6c. Type annotations pass [parallel-safe]
> sonnet

- [ ] Add type hints to all public methods across `src/`
- [ ] `mypy --strict src/` passes with zero errors
- [ ] Add `mypy` to CI

---

## Phase 7 — Multi-phase orchestration [sequential after Phase 4]

The current `PhaseExecutor` handles a single phase. Add a workflow-level runner.

### 7a. `WorkflowRunner` (`src/engine/workflow_runner.py`) [sequential]
> opus
> Depends on: Phase 4b (read methods needed to load run state)

- [ ] `WorkflowRunner` accepts an ordered list of `(phase_id, PhaseExecutor, RetryPolicy)` tuples
- [ ] Executes phases in order; stops on `ESCALATED`
- [ ] Persists overall `WorkflowRun` status at each phase boundary
- [ ] Passes output artifact from one phase as input to the next (configurable transformer fn)
- [ ] Unit tests with chained `FakePhaseExecutor` stubs

### 7b. Demo: multi-phase PRD analysis [sequential]
> sonnet
> Depends on: 7a

- [ ] Extend `demo/failure_path_runner.py` to run two phases:
  1. Input validation + LLM summarisation
  2. Safety check on the summary
- [ ] Show escalation mid-chain

---

## Delegation quick-reference

| Model   | Best for in this repo                          |
|---------|------------------------------------------------|
| haiku   | Boilerplate tests, simple clients, migrations, CI YAML |
| sonnet  | Validator logic, executor tests, SDK clients, metrics |
| opus    | Architecture (WorkflowRunner), policy design, cross-cutting decisions |

## Parallel execution map

The following groups can be dispatched simultaneously (no cross-dependencies):

```
Group A (now): 1a, 1b, 1c, 2a, 2b, 3a, 3b, 5a, 5b, 6a, 6b, 4c
Group B (after Group A tests pass): 4a, 4b, 6c
Group C (after Group B): 7a
Group D (after Group C): 7b
```
