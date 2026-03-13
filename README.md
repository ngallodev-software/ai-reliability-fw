# AI Reliability Framework

Small Python prototype for running an LLM workflow with:

- pre-call input validation,
- post-call output validation,
- retry / escalate decisions,
- persistence hooks for runs, calls, and escalations.

The current demo path is manual at the LLM boundary: you paste an LLM response into the CLI while the framework persists workflow state and decides whether to complete, retry, or escalate.

## Repository layout

- `src/core/models.py` - SQLAlchemy models and enums
- `src/db/session.py` - async DB session setup
- `src/db/repository.py` - persistence helpers
- `src/engine/decision_engine.py` - retry / escalation policy logic
- `src/engine/phase_executor.py` - end-to-end phase orchestration
- `src/validators/` - input and output validators
- `demo/failure_path_runner.py` - manual demo runner

## Bootstrap

1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start Postgres:

```bash
docker compose up -d db
```

4. Optional: configure a database URL if you do not want the default local Postgres settings:

```bash
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/reliability_fw
```

5. Apply the initial migration:

```bash
alembic upgrade head
```

## Run the demo

The demo uses `PhaseExecutor` and `ReliabilityRepository`. It seeds a workflow, prompt, and run in Postgres, asks you to paste an LLM response, and then applies the retry policy.

```bash
python demo/failure_path_runner.py
```

When prompted:

1. paste a response body,
2. press `Enter`,
3. send EOF with `Ctrl+D`.

To see the retry path, paste invalid JSON first. To see completion, paste JSON that matches the schema in `demo/fixtures.py`.

Example valid response:

```json
{
  "summary": "Authentication requirements are mostly clear, but the protocol reference is not grounded.",
  "risk_level": "HIGH",
  "missing_components": ["Grounded protocol citation", "Non-empty acceptance criteria"]
}
```

## Run tests

The smoke tests use fakes for the repository and LLM client, so they do not require Postgres.

```bash
python -m unittest tests.test_phase_executor
```

## Database notes

- Alembic is configured in `alembic.ini` and `migrations/env.py`.
- The initial migration lives in `migrations/versions/0001_initial_schema.py`.
- The demo expects the migration to be applied before you run it.

## Current status

- Core schema, repository, and executor field names are aligned.
- The phase executor now uses deterministic call IDs per run / phase / prompt / attempt for replay-safe inserts.
- The demo now exercises the repository-backed phase executor end to end.
