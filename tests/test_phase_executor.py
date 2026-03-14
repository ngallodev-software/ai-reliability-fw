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


    async def test_execute_escalates_on_safety_flag(self):
        """SAFETY_FLAG from a post-call validator triggers immediate escalation."""
        repo = FakeRepository()
        # First response triggers SAFETY_FLAG via injection in output
        # We'll use a validator that always flags safety
        from src.validators.base import BaseValidator, ValidationResult

        class AlwaysSafetyFlagValidator(BaseValidator):
            name = "always_safety"

            def validate(self, artifact, context=None):  # noqa: ARG002
                return ValidationResult(
                    pass_=False,
                    failure_category=FailureCategory.SAFETY_FLAG,
                    severity="ERROR",
                    reasons={"reason": "safety flag triggered"},
                )

        validators = [
            InputIntegrityValidator(required_fields=["title"]),
            AlwaysSafetyFlagValidator(),
        ]
        llm = FakeLLMClient(["some response"])
        executor = PhaseExecutor(repo, llm, validators)

        result = await executor.execute(
            run_id=self.run_id,
            phase_id=self.phase_id,
            prompt_id=self.prompt_id,
            input_artifact={"title": "test"},
            retry_policy=self.retry_policy,
        )

        self.assertEqual(result["status"], "ESCALATED")
        self.assertEqual(len(repo.escalations), 1)
        self.assertEqual(repo.escalations[0]["failure_category"], FailureCategory.SAFETY_FLAG)
        self.assertEqual(repo.status_updates[-1], (self.run_id, RunStatus.ESCALATED))

    async def test_execute_escalates_after_exhausting_retries(self):
        """Exhausting all retries without success results in ESCALATED status."""
        repo = FakeRepository()
        # All responses are invalid JSON — will always fail SCHEMA_VIOLATION
        llm = FakeLLMClient(["bad", "bad", "bad"])
        policy = RetryPolicy(
            max_retries=2,
            rules=[RetryRule(FailureCategory.SCHEMA_VIOLATION, "REPROMPT_WITH_ERROR_CONTEXT")],
        )
        executor = PhaseExecutor(repo, llm, self.validators)
        result = await executor.execute(
            run_id=self.run_id,
            phase_id=self.phase_id,
            prompt_id=self.prompt_id,
            input_artifact=self.input_artifact,
            retry_policy=policy,
        )

        self.assertEqual(result["status"], "ESCALATED")
        # Should have tried 3 times (attempt 0, 1, 2) then escalated
        self.assertEqual(len(repo.llm_calls), 3)
        self.assertEqual(repo.status_updates[-1], (self.run_id, RunStatus.ESCALATED))

    async def test_call_ids_are_deterministic(self):
        """Call IDs are uuid5-derived and stable across replays."""
        repo = FakeRepository()
        llm = FakeLLMClient(
            [
                "bad json",
                '{"summary":"ok","risk_level":"HIGH","missing_components":[]}',
            ]
        )
        executor = PhaseExecutor(repo, llm, self.validators)
        await executor.execute(
            run_id=self.run_id,
            phase_id=self.phase_id,
            prompt_id=self.prompt_id,
            input_artifact=self.input_artifact,
            retry_policy=self.retry_policy,
        )

        expected_id_0 = uuid.uuid5(
            uuid.NAMESPACE_URL, f"{self.run_id}:{self.phase_id}:{self.prompt_id}:0"
        )
        expected_id_1 = uuid.uuid5(
            uuid.NAMESPACE_URL, f"{self.run_id}:{self.phase_id}:{self.prompt_id}:1"
        )
        self.assertEqual(repo.llm_calls[0]["call_id"], expected_id_0)
        self.assertEqual(repo.llm_calls[1]["call_id"], expected_id_1)

    async def test_immediate_completion_on_first_valid_response(self):
        """Single valid LLM response completes with exactly one call."""
        repo = FakeRepository()
        llm = FakeLLMClient(
            ['{"summary":"all good","risk_level":"LOW","missing_components":[]}']
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
        self.assertEqual(len(repo.llm_calls), 1)
        self.assertEqual(len(repo.escalations), 0)

    async def test_llm_call_record_contains_expected_fields(self):
        """Persisted LLM call record includes all required fields."""
        repo = FakeRepository()
        llm = FakeLLMClient(
            ['{"summary":"ok","risk_level":"HIGH","missing_components":[]}']
        )
        executor = PhaseExecutor(repo, llm, self.validators)
        await executor.execute(
            run_id=self.run_id,
            phase_id=self.phase_id,
            prompt_id=self.prompt_id,
            input_artifact=self.input_artifact,
            retry_policy=self.retry_policy,
        )

        call = repo.llm_calls[0]
        self.assertIn("call_id", call)
        self.assertIn("run_id", call)
        self.assertIn("phase_id", call)
        self.assertIn("prompt_id", call)
        self.assertIn("provider", call)
        self.assertIn("model", call)
        self.assertIn("retry_attempt_num", call)
        self.assertIn("latency_ms", call)
        self.assertIn("response_raw", call)
        self.assertEqual(call["run_id"], self.run_id)
        self.assertIsNone(call["failure_category"])


if __name__ == "__main__":
    unittest.main()
