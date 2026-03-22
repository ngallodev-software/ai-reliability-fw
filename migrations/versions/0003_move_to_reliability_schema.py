"""Move all tables to reliability schema

Revision ID: 0003_reliability_schema
Revises: 0002_token_cost
Create Date: 2026-03-22

Moves workflows, prompts, workflow_runs, llm_calls, and escalation_records
from the public schema into the dedicated reliability schema.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_reliability_schema"
down_revision: Union[str, Sequence[str], None] = "0002_token_cost"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS reliability")

    # Move enum types into the reliability schema.
    # Postgres enums live in pg_catalog and are schema-scoped; rename them so
    # they're consistently namespaced. We use ALTER TYPE ... SET SCHEMA.
    op.execute("ALTER TYPE runstatus SET SCHEMA reliability")
    op.execute("ALTER TYPE failurecategory SET SCHEMA reliability")

    # Move tables.
    for table in ("workflows", "prompts", "workflow_runs", "llm_calls", "escalation_records"):
        op.execute(f"ALTER TABLE {table} SET SCHEMA reliability")


def downgrade() -> None:
    for table in ("escalation_records", "llm_calls", "workflow_runs", "prompts", "workflows"):
        op.execute(f"ALTER TABLE reliability.{table} SET SCHEMA public")

    op.execute("ALTER TYPE reliability.failurecategory SET SCHEMA public")
    op.execute("ALTER TYPE reliability.runstatus SET SCHEMA public")
