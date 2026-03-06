import unittest
import uuid

from src.core.models import FailureCategory, RunStatus
from src.engine.decision_engine import RetryPolicy, RetryRule
from src.engine.phase_executor import PhaseExecutor
from src.validators.input_schema_validator import InputIntegrityValidator
from src.validators.json_schema_validator import JsonSchemaValidator


class FakeRepository:
    def __init__(self):
        self.llm_calls = []
        self.escalations = []
        self.status_updates = []

    async def persist_llm_call(self, call_data: dict):
        self.llm_calls.append(call_data)

    async def create_escalation(self, escalation_data: dict):
        self.escalations.append(escalation_data)
        return uuid.uuid4()

    async def update_run_status(self, run_id, status):
        self.status_updates.append((run_id, status))


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def call(self, prompt: str, model: str) -> dict:
        self.calls.append({"prompt": prompt, "model": model})
        response_raw = self.responses.pop(0)
        return {
            "response_raw": response_raw,
            "latency_ms": 12,
            "provider": "TEST",
            "model": model,
        }


class PhaseExecutorSmokeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.run_id = uuid.uuid4()
        self.phase_id = uuid.uuid4()
        self.prompt_id = uuid.uuid4()
        self.retry_policy = RetryPolicy(
            max_retries=2,
            rules=[
                RetryRule(FailureCategory.SCHEMA_VIOLATION, "REPROMPT_WITH_ERROR_CONTEXT"),
                RetryRule(FailureCategory.MISSING_REQUIRED_FIELD, "REPROMPT_WITH_ERROR_CONTEXT"),
            ],
        )
        self.validators = [
            InputIntegrityValidator(required_fields=["title", "requirements"]),
            JsonSchemaValidator(
                schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "risk_level": {"type": "string"},
                        "missing_components": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["summary", "risk_level", "missing_components"],
                }
            ),
        ]
        self.input_artifact = {
            "title": "User Authentication Service",
            "requirements": [{"id": "REQ-001", "description": "Return JSON"}],
        }

    async def test_execute_completes_after_retry(self):
        repo = FakeRepository()
        llm = FakeLLMClient(
            [
                "not valid json",
                '{"summary":"ok","risk_level":"HIGH","missing_components":["citations"]}',
            ]
        )
        executor = PhaseExecutor(repo, llm, self.validators)

        result = await executor.execute(
            run_id=self.run_id,
            phase_id=self.phase_id,
            prompt_id=self.prompt_id,
            input_artifact=self.input_artifact,
            retry_policy=self.retry_policy,
        )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(len(repo.llm_calls), 2)
        self.assertEqual(repo.escalations, [])
        self.assertEqual(repo.status_updates[-1], (self.run_id, RunStatus.COMPLETED))
        self.assertEqual(repo.llm_calls[0]["call_id"], uuid.uuid5(uuid.NAMESPACE_URL, f"{self.run_id}:{self.phase_id}:{self.prompt_id}:0"))
        self.assertEqual(repo.llm_calls[1]["call_id"], uuid.uuid5(uuid.NAMESPACE_URL, f"{self.run_id}:{self.phase_id}:{self.prompt_id}:1"))

    async def test_execute_escalates_on_input_validation_failure(self):
        repo = FakeRepository()
        llm = FakeLLMClient([])
        executor = PhaseExecutor(repo, llm, self.validators)

        result = await executor.execute(
            run_id=self.run_id,
            phase_id=self.phase_id,
            prompt_id=self.prompt_id,
            input_artifact={"title": "Missing requirements"},
            retry_policy=self.retry_policy,
        )

        self.assertEqual(result["status"], "HALTED")
        self.assertEqual(len(repo.llm_calls), 0)
        self.assertEqual(len(repo.escalations), 1)
        self.assertEqual(repo.escalations[0]["failure_category"], FailureCategory.MISSING_REQUIRED_FIELD)
        self.assertEqual(repo.escalations[0]["retry_attempt_num"], 0)
        self.assertEqual(repo.status_updates[-1], (self.run_id, RunStatus.ESCALATED))


if __name__ == "__main__":
    unittest.main()
