import asyncio
import hashlib
import uuid

from rich.console import Console
from rich.table import Table

from demo.fixtures import FAILURE_PATH_PRD, PRD_ANALYSIS_SCHEMA
from src.core.models import RunStatus, FailureCategory
from src.db.repository import ReliabilityRepository
from src.db.session import async_session
from src.engine.decision_engine import RetryPolicy, RetryRule
from src.engine.phase_executor import PhaseExecutor
from src.llm.client import CLIProvider
from src.validators.input_schema_validator import InputIntegrityValidator
from src.validators.json_schema_validator import JsonSchemaValidator

console = Console()


async def seed_demo_records(repo: ReliabilityRepository, prompt_text: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    workflow_id = uuid.uuid4()
    prompt_id = uuid.uuid4()
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
    await repo.persist_prompt(
        {
            "prompt_id": prompt_id,
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
        executor = PhaseExecutor(repo, CLIProvider(), validators)

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


if __name__ == "__main__":
    asyncio.run(run_failure_demo())
