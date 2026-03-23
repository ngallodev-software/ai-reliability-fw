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

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.core.models import FailureCategory, RunStatus
from src.db.repository import ReliabilityRepository

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://user:pass@localhost:5432/reliability_fw",
)


def make_engine():
    return create_async_engine(
        DB_URL,
        echo=False,
        connect_args={"server_settings": {"search_path": "reliability,public"}},
    )


@unittest.skipUnless(
    os.getenv("DATABASE_URL") or os.getenv("POSTGRES_AVAILABLE"),
    "Set DATABASE_URL or POSTGRES_AVAILABLE=1 to run DB integration tests",
)
class RepositoryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = make_engine()
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)
        self.session = self.Session()
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
                "status": RunStatus.RUNNING,
            }
        )

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    # --- Write path ---

    async def test_persist_llm_call_succeeds(self):
        call_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{self.run_id}:phase1:{self.prompt_id}:0")
        await self.repo.persist_llm_call(
            {
                "call_id": call_id,
                "run_id": self.run_id,
                "phase_id": uuid.uuid4(),
                "prompt_id": self.prompt_id,
                "provider": "TEST",
                "model": "fake-model",
                "retry_attempt_num": 0,
                "latency_ms": 42,
                "response_raw": '{"result": "ok"}',
                "failure_category": None,
            }
        )
        calls = await self.repo.get_calls_for_run(self.run_id)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].call_id, call_id)

    async def test_persist_llm_call_is_idempotent(self):
        """Re-inserting with the same call_id should silently do nothing."""
        call_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{self.run_id}:phase1:{self.prompt_id}:0")
        call_data = {
            "call_id": call_id,
            "run_id": self.run_id,
            "phase_id": uuid.uuid4(),
            "prompt_id": self.prompt_id,
            "provider": "TEST",
            "model": "fake-model",
            "retry_attempt_num": 0,
            "latency_ms": 10,
            "response_raw": "first",
            "failure_category": None,
        }
        await self.repo.persist_llm_call(call_data)
        await self.repo.persist_llm_call(call_data)  # duplicate — should not raise
        calls = await self.repo.get_calls_for_run(self.run_id)
        self.assertEqual(len(calls), 1)

    async def test_persist_llm_call_with_token_cost_columns(self):
        """Token cost columns (nullable) can be written and read back."""
        call_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{self.run_id}:phase2:{self.prompt_id}:0")
        await self.repo.persist_llm_call(
            {
                "call_id": call_id,
                "run_id": self.run_id,
                "phase_id": uuid.uuid4(),
                "prompt_id": self.prompt_id,
                "provider": "FAKE",
                "model": "fake-v1",
                "retry_attempt_num": 0,
                "latency_ms": 55,
                "response_raw": "{}",
                "failure_category": None,
                "input_tokens": 100,
                "output_tokens": 50,
                "token_cost_usd": 0.0,
            }
        )
        calls = await self.repo.get_calls_for_run(self.run_id)
        call = next(c for c in calls if c.call_id == call_id)
        self.assertEqual(call.input_tokens, 100)
        self.assertEqual(call.output_tokens, 50)
        self.assertEqual(call.token_cost_usd, 0.0)

    async def test_persist_prompt_reuses_existing_prompt_hash(self):
        """Re-seeding the same prompt text should return the canonical prompt_id."""
        prompt_text = "Stable prompt text"
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
        first_prompt_id = uuid.uuid4()
        second_prompt_id = uuid.uuid4()

        persisted_first = await self.repo.persist_prompt(
            {
                "prompt_id": first_prompt_id,
                "content": prompt_text,
                "prompt_hash": prompt_hash,
                "version_tag": "demo-v1",
            }
        )
        persisted_second = await self.repo.persist_prompt(
            {
                "prompt_id": second_prompt_id,
                "content": prompt_text,
                "prompt_hash": prompt_hash,
                "version_tag": "demo-v2",
            }
        )

        self.assertEqual(persisted_first, first_prompt_id)
        self.assertEqual(persisted_second, first_prompt_id)

    async def test_create_escalation_returns_id(self):
        esc_id = await self.repo.create_escalation(
            {
                "run_id": self.run_id,
                "phase_id": uuid.uuid4(),
                "llm_call_id": None,
                "failure_category": FailureCategory.SCHEMA_VIOLATION,
                "retry_attempt_num": 0,
                "trigger_reason": "Schema mismatch on attempt 0",
            }
        )
        self.assertIsNotNone(esc_id)

    async def test_update_run_status(self):
        await self.repo.update_run_status(self.run_id, RunStatus.COMPLETED)
        run = await self.repo.get_run(self.run_id)
        self.assertEqual(run.status, RunStatus.COMPLETED)

    async def test_update_run_status_is_idempotent(self):
        """Updating to the same status twice should not raise."""
        await self.repo.update_run_status(self.run_id, RunStatus.COMPLETED)
        await self.repo.update_run_status(self.run_id, RunStatus.COMPLETED)
        run = await self.repo.get_run(self.run_id)
        self.assertEqual(run.status, RunStatus.COMPLETED)

    # --- Read path ---

    async def test_get_run_returns_run(self):
        run = await self.repo.get_run(self.run_id)
        self.assertIsNotNone(run)
        self.assertEqual(run.run_id, self.run_id)
        self.assertEqual(run.status, RunStatus.RUNNING)

    async def test_get_run_unknown_id_returns_none(self):
        result = await self.repo.get_run(uuid.uuid4())
        self.assertIsNone(result)

    async def test_get_calls_for_run_ordered_by_attempt(self):
        phase_id = uuid.uuid4()
        for attempt in range(3):
            call_id = uuid.uuid5(
                uuid.NAMESPACE_URL, f"{self.run_id}:{phase_id}:{self.prompt_id}:{attempt}"
            )
            await self.repo.persist_llm_call(
                {
                    "call_id": call_id,
                    "run_id": self.run_id,
                    "phase_id": phase_id,
                    "prompt_id": self.prompt_id,
                    "provider": "TEST",
                    "model": "fake",
                    "retry_attempt_num": attempt,
                    "latency_ms": 10,
                    "response_raw": "{}",
                    "failure_category": None,
                }
            )
        calls = await self.repo.get_calls_for_run(self.run_id)
        attempt_nums = [c.retry_attempt_num for c in calls]
        self.assertEqual(attempt_nums, sorted(attempt_nums))

    async def test_get_escalations_for_run(self):
        await self.repo.create_escalation(
            {
                "run_id": self.run_id,
                "phase_id": uuid.uuid4(),
                "llm_call_id": None,
                "failure_category": FailureCategory.SAFETY_FLAG,
                "retry_attempt_num": 1,
                "trigger_reason": "Blocked content detected",
            }
        )
        escalations = await self.repo.get_escalations_for_run(self.run_id)
        self.assertEqual(len(escalations), 1)
        self.assertEqual(escalations[0].failure_category, FailureCategory.SAFETY_FLAG)

    async def test_get_escalations_empty_for_clean_run(self):
        other_run_id = uuid.uuid4()
        await self.repo.persist_run(
            {
                "run_id": other_run_id,
                "workflow_id": self.workflow_id,
                "status": RunStatus.RUNNING,
            }
        )
        escalations = await self.repo.get_escalations_for_run(other_run_id)
        self.assertEqual(escalations, [])


if __name__ == "__main__":
    unittest.main()
