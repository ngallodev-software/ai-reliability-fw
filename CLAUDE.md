# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Setup** (one-time):
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
docker compose up -d db
alembic upgrade head
```

**Run tests** (no Postgres required — uses in-memory fakes):
```bash
python3 -m unittest tests.test_phase_executor
```

**Run a single test method:**
```bash
python3 -m unittest tests.test_phase_executor.PhaseExecutorSmokeTests.test_execute_completes_after_retry
```

**Run the interactive demo** (requires Postgres):
```bash
python3 demo/failure_path_runner.py
```

**Apply migrations:**
```bash
alembic upgrade head
alembic downgrade -1
```

## Architecture

This is a Python prototype for an LLM reliability layer. The core flow is: validate input → call LLM → validate output → decide (complete / retry / escalate) → persist.

### Layer overview

- **`src/core/models.py`** — SQLAlchemy ORM models (`Workflow`, `WorkflowRun`, `LLMCall`, `Prompt`, `EscalationRecord`) and the two enums used throughout: `FailureCategory` and `RunStatus`.

- **`src/engine/phase_executor.py`** — `PhaseExecutor` orchestrates a single phase: runs the input validator first (`validators[0]`), enters the retry loop calling the LLM, runs post-call validators (`validators[1:]`), calls the decision engine, and persists every outcome. Call IDs are deterministic (`uuid5`) for replay-safe idempotency.

- **`src/engine/decision_engine.py`** — Pure function `decide(failures, policy, attempt_num)` that maps failure categories to RETRY / ESCALATE / COMPLETE actions using a `RetryPolicy` (list of `RetryRule`s). `SAFETY_FLAG` and `INPUT_VALIDATION_ERROR` always escalate immediately.

- **`src/validators/`** — Validators all extend `BaseValidator` and return `ValidationResult(pass_, failure_category, severity, reasons)`. `InputIntegrityValidator` (pre-call) checks required fields on the input dict; `JsonSchemaValidator` (post-call) validates LLM output against a JSON Schema.

- **`src/db/repository.py`** — `ReliabilityRepository` wraps async SQLAlchemy sessions. All inserts use `ON CONFLICT DO NOTHING` for idempotency. `update_run_status` guards against redundant transitions.

- **`src/db/session.py`** — Async engine configured via `DATABASE_URL` env var (default: `postgresql+asyncpg://user:pass@localhost:5432/reliability_fw`). Load via `.env` or export before running.

- **`migrations/`** — Alembic migrations. The single migration `0001_initial_schema.py` creates all tables and Postgres enums.

### Key design constraints

- `PhaseExecutor.validators[0]` is always the input validator; post-call validators are `validators[1:]`. This ordering is a hard convention, not enforced by type.
- LLM call IDs are `uuid5(NAMESPACE_URL, "{run_id}:{phase_id}:{prompt_id}:{attempt_num}")` — replaying the same inputs produces the same ID, which the `ON CONFLICT DO NOTHING` insert silently deduplicates.
- The `llm_client` passed to `PhaseExecutor` must be an async object with `call(prompt: str, model: str) -> dict` returning `{response_raw, latency_ms, provider, model}`. The demo uses a manual CLI client; tests use `FakeLLMClient`.
- DB default connection uses `user`/`pass`/`reliability_fw` matching `docker-compose.yml`.
