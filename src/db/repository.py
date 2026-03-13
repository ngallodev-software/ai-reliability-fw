from uuid import UUID
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import update, select
from src.core.models import Prompt, Workflow, LLMCall, EscalationRecord, WorkflowRun, RunStatus

class ReliabilityRepository:
    def __init__(self, session):
        self.session = session

    async def persist_workflow(self, workflow_data: dict):
        stmt = insert(Workflow).values(**workflow_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["workflow_id"])
        await self.session.execute(stmt)
        await self.session.commit()

    async def persist_prompt(self, prompt_data: dict):
        stmt = insert(Prompt).values(**prompt_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["prompt_id"])
        await self.session.execute(stmt)
        await self.session.commit()

    async def persist_run(self, run_data: dict):
        stmt = insert(WorkflowRun).values(**run_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["run_id"])
        await self.session.execute(stmt)
        await self.session.commit()

    async def persist_llm_call(self, call_data: dict):
        """Idempotent insert of an LLM call record."""
        stmt = insert(LLMCall).values(**call_data)
        # Prevents duplicate records if a phase is re-played
        stmt = stmt.on_conflict_do_nothing(index_elements=["call_id"])
        await self.session.execute(stmt)
        await self.session.commit()

    async def create_escalation(self, escalation_data: dict):
        """Creates an escalation record for the run and optional LLM call."""
        stmt = insert(EscalationRecord).values(**escalation_data).returning(EscalationRecord.escalation_id)
        result = await self.session.execute(stmt)
        esc_id = result.scalar_one()
        await self.session.commit()
        return esc_id

    async def update_run_status(self, run_id: UUID, status: RunStatus):
        """Atomic status update with idempotency guard."""
        await self.session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.run_id == run_id)
            .where(WorkflowRun.status != status)
            .values(status=status)
        )
        await self.session.commit()

    async def get_run(self, run_id: UUID) -> WorkflowRun | None:
        result = await self.session.execute(
            select(WorkflowRun).where(WorkflowRun.run_id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_calls_for_run(self, run_id: UUID) -> list[LLMCall]:
        result = await self.session.execute(
            select(LLMCall)
            .where(LLMCall.run_id == run_id)
            .order_by(LLMCall.retry_attempt_num)
        )
        return list(result.scalars().all())

    async def get_escalations_for_run(self, run_id: UUID) -> list[EscalationRecord]:
        result = await self.session.execute(
            select(EscalationRecord).where(EscalationRecord.run_id == run_id)
        )
        return list(result.scalars().all())
