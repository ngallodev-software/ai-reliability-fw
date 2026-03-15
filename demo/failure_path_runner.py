import asyncio
import hashlib
import json
import sys
import uuid
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.table import Table

from demo.fixtures import FAILURE_PATH_PRD, PRD_ANALYSIS_SCHEMA
from src.core.models import RunStatus, FailureCategory
from src.db.repository import ReliabilityRepository
from src.db.session import async_session
from src.engine.decision_engine import RetryPolicy, RetryRule
from src.engine.phase_executor import PhaseExecutor
from src.llm.client import BaseLLMClient
from src.validators.input_schema_validator import InputIntegrityValidator
from src.validators.json_schema_validator import JsonSchemaValidator

console = Console()


class FakeLLMClient(BaseLLMClient):
    """Scripted fake LLM client for demo use — no API keys required.

    Each call() pops the next response from the list.  The last response is
    repeated if the list is exhausted (supports open-ended retry loops).
    Fake token costs are included so the token_cost_usd column is populated.
    """

    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    async def call(self, prompt: str, model: str) -> dict:  # prompt ignored — scripted responses
        response = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        return {
            "response_raw": response,
            "latency_ms": 120,
            "provider": "FAKE",
            "model": model,
            "input_tokens": 200,
            "output_tokens": 80,
            "token_cost_usd": 0.0,
        }


# Scripted responses that mirror a realistic failure → retry → success path:
#   Attempt 0 — invalid JSON (SCHEMA_VIOLATION, triggers retry)
#   Attempt 1 — valid JSON but missing "risk_level" (SCHEMA_VIOLATION, triggers retry)
#   Attempt 2 — well-formed, schema-valid response (COMPLETE)
DEMO_RESPONSES = [
    "sorry, I don't understand the task",
    json.dumps({"summary": "Authentication service has unverified entity ZephyrAuth"}),
    json.dumps(
        {
            "summary": "Authentication service references ungrounded entity 'ZephyrAuth'. "
                       "No citations support it.",
            "risk_level": "HIGH",
            "missing_components": ["grounding citation for ZephyrAuth", "acceptance criteria"],
        }
    ),
]


async def seed_demo_records(
    repo: ReliabilityRepository, prompt_text: str
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    workflow_id = uuid.uuid4()
    run_id = uuid.uuid4()

    await repo.persist_workflow(
        {
            "workflow_id": workflow_id,
            "name": "failure-path-demo",
            "version": "1.0",
            "definition_json": {
                "entry_phase": "prd-analysis",
                "validators": ["input_integrity_validator", "json_schema_validator"],
            },
        }
    )
    prompt_id = await repo.persist_prompt(
        {
            "prompt_id": uuid.uuid4(),
            "content": prompt_text,
            "prompt_hash": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            "version_tag": "demo-v1",
        }
    )
    await repo.persist_run(
        {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "status": RunStatus.RUNNING,
        }
    )
    return workflow_id, prompt_id, run_id


async def run_failure_demo():
    console.print("[bold reverse yellow] STARTING RELIABILITY DEMO: FAILURE PATH [/]\n")

    policy = RetryPolicy(
        max_retries=2,
        rules=[
            RetryRule(FailureCategory.SCHEMA_VIOLATION, "REPROMPT_WITH_ERROR_CONTEXT"),
            RetryRule(FailureCategory.MISSING_REQUIRED_FIELD, "REPROMPT_WITH_ERROR_CONTEXT"),
        ],
    )

    validators = [
        InputIntegrityValidator(required_fields=["title", "requirements"]),
        JsonSchemaValidator(schema=PRD_ANALYSIS_SCHEMA),
    ]
    prompt = f"Analyze this PRD and return JSON matching the schema: {FAILURE_PATH_PRD}"

    async with async_session() as session:
        repo = ReliabilityRepository(session)
        executor = PhaseExecutor(repo, FakeLLMClient(DEMO_RESPONSES), validators)

        try:
            _, prompt_id, run_id = await seed_demo_records(repo, prompt)
        except Exception as exc:
            console.print("[bold red]Database setup failed.[/]")
            console.print(
                "Run `docker compose up -d db` and `alembic upgrade head`, "
                "then retry this demo."
            )
            console.print(f"[dim]{type(exc).__name__}: {exc}[/]")
            return

        console.print(f"[dim]run_id: {run_id}[/]\n")

        result = await executor.execute(
            run_id=run_id,
            phase_id=uuid.uuid4(),
            prompt_id=prompt_id,
            input_artifact=FAILURE_PATH_PRD,
            retry_policy=policy,
        )

        table = Table(title="Execution Result")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="magenta")
        for key, value in result.items():
            table.add_row(key, str(value))
        console.print(table)

        console.print("\n[dim]Query to inspect stored calls:[/]")
        console.print(
            f"[dim]SELECT provider, model, latency_ms, input_tokens, output_tokens, "
            f"token_cost_usd FROM llm_calls WHERE run_id = '{run_id}';[/]"
        )


if __name__ == "__main__":
    asyncio.run(run_failure_demo())
