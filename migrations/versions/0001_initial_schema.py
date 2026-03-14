"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-06 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


failure_category_enum = postgresql.ENUM(
    "SCHEMA_VIOLATION",
    "HALLUCINATION_SIGNAL",
    "MISSING_REQUIRED_FIELD",
    "SAFETY_FLAG",
    "TIMEOUT",
    "PROVIDER_ERROR",
    "HUMAN_ESCALATED",
    "VALIDATION_FAILURE",
    "INPUT_VALIDATION_ERROR",
    name="failurecategory",
    create_type=False,
)

run_status_enum = postgresql.ENUM(
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "ESCALATED",
    "REPLAYING",
    name="runstatus",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    failure_category_enum.create(bind, checkfirst=True)
    run_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "workflows",
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("definition_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("workflow_id"),
    )

    op.create_table(
        "prompts",
        sa.Column("prompt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("prompt_hash", sa.String(), nullable=False),
        sa.Column("version_tag", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("prompt_id"),
        sa.UniqueConstraint("prompt_hash"),
    )

    op.create_table(
        "workflow_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", run_status_enum, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.workflow_id"]),
        sa.PrimaryKeyConstraint("run_id"),
    )

    op.create_table(
        "llm_calls",
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("retry_attempt_num", sa.Integer(), nullable=True),
        sa.Column("failure_category", failure_category_enum, nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("response_raw", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompts.prompt_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.run_id"]),
        sa.PrimaryKeyConstraint("call_id"),
    )

    op.create_table(
        "escalation_records",
        sa.Column("escalation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("llm_call_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("retry_attempt_num", sa.Integer(), nullable=False),
        sa.Column("failure_category", failure_category_enum, nullable=False),
        sa.Column("trigger_reason", sa.String(length=500), nullable=False),
        sa.Column("escalated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["llm_call_id"], ["llm_calls.call_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.run_id"]),
        sa.PrimaryKeyConstraint("escalation_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("escalation_records")
    op.drop_table("llm_calls")
    op.drop_table("workflow_runs")
    op.drop_table("prompts")
    op.drop_table("workflows")

    bind = op.get_bind()
    run_status_enum.drop(bind, checkfirst=True)
    failure_category_enum.drop(bind, checkfirst=True)
