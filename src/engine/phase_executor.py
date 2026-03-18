import uuid
from typing import Any, Sequence
from src.core.models import FailureCategory, RunStatus
from src.engine.decision_engine import decide, RetryPolicy
from src.validators.base import BaseValidator
from src.db.repository import ReliabilityRepository

class PhaseExecutor:
    """
    Orchestrates a single phase execution including validation, 
    LLM interaction, and automated retry/escalation logic.
    """
    def __init__(self, repository: ReliabilityRepository, llm_client, validators: Sequence[BaseValidator]):
        self.repo = repository
        self.llm = llm_client
        self.validators = validators

    async def execute(self, run_id: uuid.UUID, phase_id: uuid.UUID, prompt_id: uuid.UUID, input_artifact: Any, retry_policy: RetryPolicy):
        attempt_num = 0
        
        # 1. Pre-call Input Validation
        # (Assuming the first validator in the list is the InputSchemaValidator)
        input_val = self.validators[0].validate(input_artifact)
        if not input_val.pass_:
            await self.repo.create_escalation({
                "run_id": run_id,
                "phase_id": phase_id,
                "failure_category": input_val.failure_category or FailureCategory.INPUT_VALIDATION_ERROR,
                "retry_attempt_num": 0,
                "trigger_reason": str(input_val.reasons)
            })
            await self.repo.update_run_status(run_id, RunStatus.ESCALATED)
            return {"status": "HALTED", "reason": "Input validation error"}

        # 2. LLM Interaction & Retry Loop
        while attempt_num <= retry_policy.max_retries:
            # Use a stable key so retries/replays can be persisted idempotently.
            call_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}:{phase_id}:{prompt_id}:{attempt_num}")
            
            # Call the LLM (Manual CLI for Phase 1 demo)
            llm_result = await self.llm.call(str(input_artifact))
            
            # Post-call Validation
            failures = []
            for validator in self.validators[1:]:  # Skip input validator
                res = validator.validate(llm_result["response_raw"])
                if not res.pass_:
                    failures.append(res.failure_category)

            # Persist the LLMCall record BEFORE decision
            call_record = {
                "call_id": call_id,
                "run_id": run_id,
                "phase_id": phase_id,
                "prompt_id": prompt_id,
                "provider": llm_result["provider"],
                "model": llm_result["model"],
                "retry_attempt_num": attempt_num,
                "latency_ms": llm_result["latency_ms"],
                "response_raw": llm_result["response_raw"],
                "failure_category": failures[0] if failures else None,
                "input_tokens": llm_result.get("input_tokens"),
                "output_tokens": llm_result.get("output_tokens"),
                "token_cost_usd": llm_result.get("token_cost_usd"),
            }
            await self.repo.persist_llm_call(call_record)

            # 3. Decision Engine
            decision = decide(failures, retry_policy, attempt_num)
            
            if decision.action == "COMPLETE":
                await self.repo.update_run_status(run_id, RunStatus.COMPLETED)
                return {
                    "status": "SUCCESS",
                    "artifact": llm_result["response_raw"],
                    "call_id": str(call_id),
                    "provider": llm_result["provider"],
                    "model": llm_result["model"],
                    "latency_ms": llm_result["latency_ms"],
                    "input_tokens": llm_result.get("input_tokens"),
                    "output_tokens": llm_result.get("output_tokens"),
                    "token_cost_usd": llm_result.get("token_cost_usd"),
                }
            
            if decision.action == "ESCALATE":
                await self.repo.create_escalation({
                    "run_id": run_id,
                    "phase_id": phase_id,
                    "llm_call_id": call_id,
                    "failure_category": failures[0] if failures else FailureCategory.HUMAN_ESCALATED,
                    "retry_attempt_num": attempt_num,
                    "trigger_reason": decision.reason
                })
                await self.repo.update_run_status(run_id, RunStatus.ESCALATED)
                return {"status": "ESCALATED", "reason": decision.reason}

            # If action is RETRY, loop continues
            attempt_num += 1

        return {"status": "FAILED", "reason": "Max retries exceeded without completion"}
