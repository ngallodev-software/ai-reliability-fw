# Architecture Decision Record — ai-reliability-fw

> Last updated: 2026-03-16

## PURPOSE
Python prototype for an LLM reliability layer that wraps any async LLM client with structured input validation, output validation, retry logic, escalation handling, and full DB persistence. Goal: make LLM-powered workflows observable, reproducible, and safe to operate in production.

## STACK
- **Language**: Python 3.x (async/await throughout)
- **ORM**: SQLAlchemy 2.x with async engine (`asyncpg` driver)
- **Database**: PostgreSQL (Docker Compose for local dev; `reliability_fw` DB, `user`/`pass` credentials)
- **Migrations**: Alembic (sequential versioned migrations in `migrations/versions/`)
- **Testing**: `unittest` + in-memory fakes (no Postgres required for unit tests; `test_repository` needs Postgres)
- **Config**: Environment variables only (`DATABASE_URL`); no YAML, no settings class, no DI framework
- **Packaging**: `pyproject.toml`

## ARCHITECTURE
Six-layer structure with strict directionality:

```
entry points (demo/, tests/)
    ↓
engine layer (PhaseExecutor, decision_engine)
    ↓
validators layer (BaseValidator, InputIntegrityValidator, JsonSchemaValidator, ContentValidator, SafetyValidator)
    ↓
db layer (ReliabilityRepository, session)
    ↓
core layer (models.py — ORM models + enums)
    ↓
PostgreSQL
```

**Key execution flow** (`PhaseExecutor.execute`):
1. Pre-call: `validators[0]` runs input validation; failure → immediate escalation + HALTED
2. Retry loop: deterministic `call_id = uuid5(run_id:phase_id:prompt_id:attempt_num)`
3. LLM call via `llm_client.call(str(input_artifact), model=...)`
4. Post-call: `validators[1:]` run against `response_raw`
5. `decide(failures, retry_policy, attempt_num)` → COMPLETE / RETRY / ESCALATE
6. `persist_llm_call()` before decision; `create_escalation()` + `update_run_status()` on terminal outcomes
7. Returns full call metadata on SUCCESS (status, artifact, call_id, provider, model, latency_ms, token fields)

**DB schema summary:**
- `workflows` → `workflow_runs` (FK) → `llm_calls` (FK) + `escalation_records` (FK)
- `prompts` → `llm_calls` (FK)
- All PKs are UUID4 except `llm_calls.call_id` which is deterministic UUID5
- `phase_id` is a UUID passed by caller — no FK, no `phases` table; purely a logical grouping key

**Caller responsibility**: must pre-create `Workflow`, `Prompt`, and `WorkflowRun` rows before calling `execute()`. Session is passed in via constructor DI on `ReliabilityRepository`.

## PATTERNS
- **Idempotent inserts**: all `persist_*` methods use `ON CONFLICT DO NOTHING` — safe to replay
- **Deterministic call IDs**: `uuid5(NAMESPACE_URL, "{run_id}:{phase_id}:{prompt_id}:{attempt_num}")` — replaying same inputs deduplicates silently
- **Validators[0] convention**: first validator is always the pre-call input validator; `validators[1:]` are post-call. Hard convention, not type-enforced.
- **Pure decision engine**: `decide(failures, policy, attempt_num)` is a pure function — no I/O, no side effects, fully unit-testable
- **Fake LLM client for tests**: `FakeLLMClient` with scripted responses used in all unit tests and demo — no real LLM calls needed
- **Manual DI**: `PhaseExecutor(repo, llm_client, validators)` — all dependencies passed explicitly, no framework
- **Status guard**: `update_run_status` is atomic and idempotent — safe to call multiple times

## TRADEOFFS
- **No `phases` table**: `phase_id` is an opaque UUID FK to nothing. Keeps schema simple at the cost of no phase-level metadata or ordering queries.
- **Hardcoded model name**: `"claude-3-sonnet"` is hardcoded in `PhaseExecutor.execute()` — not configurable per-call yet (Phase 2 work).
- **No `WorkflowRunner`**: multi-phase orchestration not yet implemented. Each phase is wired manually by the caller (Phase 7 roadmap).
- **validators[0] ordering**: the input-validator-first convention is implicit. A misconfigured list silently skips pre-call validation.
- **Token cost columns nullable**: `input_tokens`, `output_tokens`, `token_cost_usd` on `llm_calls` are nullable — LLM clients that don't return token data still persist cleanly.
- **Sync validators in async executor**: `validator.validate()` is synchronous; fine for CPU-bound regex/schema checks but would block if validators ever do I/O.

## PHILOSOPHY
- **Correctness over cleverness**: deterministic IDs and `ON CONFLICT DO NOTHING` make every operation safe to retry without coordination.
- **No magic**: explicit constructor DI, env-var config, manual session management. Easy to trace what runs where.
- **Separation of concerns**: `decide()` knows nothing about DB; `PhaseExecutor` knows nothing about SQL; validators know nothing about retry state.
- **Test without infra**: all business logic (decision engine, validators, executor) is testable with in-memory fakes. DB tests are isolated to `test_repository`.
- **Incremental complexity**: Phase 1 MVP proves the core loop works. Real LLM clients, multi-phase orchestration, and observability are layered on later without changing the core contract.
