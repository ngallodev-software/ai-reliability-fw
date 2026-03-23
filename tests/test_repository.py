"""Integration tests for ReliabilityRepository — requires a live Postgres instance.

Run with:
    docker compose up -d db
    alembic upgrade head
    python -m unittest tests.test_repository
"""
import hashlib
import os
import unittest
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.models import FailureCategory, RunStatus
from src.db.repository import ReliabilityRepository
from src.db.session import init_reliability, get_db

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://user:pass@localhost:5432/reliability_fw",
)


@unittest.skipUnless(
    os.getenv("DATABASE_URL") or os.getenv("POSTGRES_AVAILABLE"),
    "Set DATABASE_URL or POSTGRES_AVAILABLE=1 to run DB integration tests",
)
class RepositoryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        init_reliability(DB_URL)

        # Drive get_db() manually to get a session for the test.
        self._db_gen = get_db()
        self.session = await anext(self._db_gen)
        self.repo = ReliabilityRepository(self.session)

        # Seed a workflow + prompt + run that tests can use
        self.workflow_id = uuid.uuid4()
        self.prompt_id = uuid.uuid4()
        self.run_id = uuid.uuid4()
        prompt_text = f"Test prompt {self.prompt_id}"

        await self.repo.persist_workflow(
            {
                "workflow_id": self.workflow_id,
                "name": "test-workflow",
                "version": "1.0",
                "definition_json": {"entry_phase": "test"},
            }
        )
        await self.repo.persist_prompt(
            {
                "prompt_id": self.prompt_id,
                "content": prompt_text,
                "prompt_hash": hashlib.sha256(prompt_text.encode()).hexdigest(),
                "version_tag": "test-v1",
            }
        )
        await self.repo.persist_run(
            {
                "run_id": self.run_id,
                "workflow_id": self.workflow_id,
            }
        )

    async def asyncTearDown(self):
        await self.session.close()
        await self._db_gen.aclose()

    async def test_persist_llm_call_succeeds(self):
        call_id = uuid.uuid4()
        await self.repo.persist_llm_call(
            {
                "call_id": call_id,
                "run_id": self.run_id,
                "phase_id": uuid.uuid4(),
                "prompt_id": self.prompt_id,
                "provider": "test",
                "model": "test-model",
                "retry_attempt_num": 0,
                "latency_ms": 100,
                "response_raw": '{"result": "ok"}',
                "failure_category": None,
            }
        )
        calls = await self.repo.get_calls_for_run(self.run_id)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].call_id, call_id)

    async def test_persist_llm_call_with_token_cost_columns(self):
        call_id = uuid.uuid4()
        await self.repo.persist_llm_call(
            {
                "call_id": call_id,
                "run_id": self.run_id,
                "phase_id": uuid.uuid4(),
                "prompt_id": self.prompt_id,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "retry_attempt_num": 0,
                "latency_ms": 200,
                "response_raw": '{"label": "phishing"}',
                "failure_category": None,
                "input_tokens": 512,
                "output_tokens": 64,
                "token_cost_usd": 0.0003,
            }
        )
        calls = await self.repo.get_calls_for_run(self.run_id)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].input_tokens, 512)
        self.assertAlmostEqual(float(calls[0].token_cost_usd), 0.0003, places=6)

    async def test_persist_llm_call_is_idempotent(self):
        call_id = uuid.uuid4()
        record = {
            "call_id": call_id,
            "run_id": self.run_id,
            "phase_id": uuid.uuid4(),
            "prompt_id": self.prompt_id,
            "provider": "test",
            "model": "test-model",
            "retry_attempt_num": 0,
            "latency_ms": 50,
            "response_raw": "{}",
            "failure_category": None,
        }
        await self.repo.persist_llm_call(record)
        await self.repo.persist_llm_call(record)  # second call must not raise
        calls = await self.repo.get_calls_for_run(self.run_id)
        self.assertEqual(len(calls), 1)

    async def test_persist_prompt_reuses_existing_prompt_hash(self):
        text = "Duplicate prompt"
        h = hashlib.sha256(text.encode()).hexdigest()
        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()
        r1 = await self.repo.persist_prompt(
            {"prompt_id": pid1, "content": text, "prompt_hash": h, "version_tag": "v1"}
        )
        r2 = await self.repo.persist_prompt(
            {"prompt_id": pid2, "content": text, "prompt_hash": h, "version_tag": "v1"}
        )
        self.assertEqual(r1, r2)

    async def test_get_run_returns_run(self):
        run = await self.repo.get_run(self.run_id)
        self.assertIsNotNone(run)
        self.assertEqual(run.run_id, self.run_id)

    async def test_get_run_unknown_id_returns_none(self):
        result = await self.repo.get_run(uuid.uuid4())
        self.assertIsNone(result)

    async def test_update_run_status(self):
        await self.repo.update_run_status(self.run_id, RunStatus.COMPLETED)
        run = await self.repo.get_run(self.run_id)
        self.assertEqual(run.status, RunStatus.COMPLETED)

    async def test_update_run_status_is_idempotent(self):
        await self.repo.update_run_status(self.run_id, RunStatus.COMPLETED)
        await self.repo.update_run_status(self.run_id, RunStatus.COMPLETED)
        run = await self.repo.get_run(self.run_id)
        self.assertEqual(run.status, RunStatus.COMPLETED)

    async def test_create_escalation_returns_id(self):
        esc_id = await self.repo.create_escalation(
            {
                "run_id": self.run_id,
                "phase_id": uuid.uuid4(),
                "failure_category": FailureCategory.SCHEMA_VIOLATION,
                "retry_attempt_num": 1,
                "trigger_reason": "bad json",
            }
        )
        self.assertIsNotNone(esc_id)

    async def test_get_escalations_for_run(self):
        await self.repo.create_escalation(
            {
                "run_id": self.run_id,
                "phase_id": uuid.uuid4(),
                "failure_category": FailureCategory.HUMAN_ESCALATED,
                "retry_attempt_num": 0,
                "trigger_reason": "test",
            }
        )
        escalations = await self.repo.get_escalations_for_run(self.run_id)
        self.assertEqual(len(escalations), 1)

    async def test_get_escalations_empty_for_clean_run(self):
        fresh_run_id = uuid.uuid4()
        await self.repo.persist_run({"run_id": fresh_run_id, "workflow_id": self.workflow_id})
        escalations = await self.repo.get_escalations_for_run(fresh_run_id)
        self.assertEqual(len(escalations), 0)

    async def test_get_calls_for_run_ordered_by_attempt(self):
        phase_id = uuid.uuid4()
        for attempt in range(3):
            await self.repo.persist_llm_call(
                {
                    "call_id": uuid.uuid4(),
                    "run_id": self.run_id,
                    "phase_id": phase_id,
                    "prompt_id": self.prompt_id,
                    "provider": "test",
                    "model": "test-model",
                    "retry_attempt_num": attempt,
                    "latency_ms": 10 * attempt,
                    "response_raw": "{}",
                    "failure_category": None,
                }
            )
        calls = await self.repo.get_calls_for_run(self.run_id)
        attempts = [c.retry_attempt_num for c in calls]
        self.assertEqual(attempts, sorted(attempts))
