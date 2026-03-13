"""Add OUTPUT_CONTENT_ERROR enum value and token cost columns to llm_calls

Revision ID: 0002_token_cost
Revises: 0001_initial_schema
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_token_cost'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add OUTPUT_CONTENT_ERROR to the failurecategory Postgres enum
    op.execute("ALTER TYPE failurecategory ADD VALUE IF NOT EXISTS 'OUTPUT_CONTENT_ERROR'")

    # Add token tracking columns to llm_calls
    op.add_column('llm_calls', sa.Column('input_tokens', sa.Integer(), nullable=True))
    op.add_column('llm_calls', sa.Column('output_tokens', sa.Integer(), nullable=True))
    op.add_column('llm_calls', sa.Column('token_cost_usd', sa.Float(), nullable=True))

    # Add composite index for common query pattern: look up calls by run and attempt
    op.create_index(
        'ix_llm_calls_run_id_attempt',
        'llm_calls',
        ['run_id', 'retry_attempt_num'],
    )


def downgrade() -> None:
    # Remove the composite index
    op.drop_index('ix_llm_calls_run_id_attempt', table_name='llm_calls')

    # Remove token tracking columns
    op.drop_column('llm_calls', 'token_cost_usd')
    op.drop_column('llm_calls', 'output_tokens')
    op.drop_column('llm_calls', 'input_tokens')

    # Removing an enum value in Postgres requires recreating the type.
    # Rename the current type, create a new one without OUTPUT_CONTENT_ERROR,
    # migrate both columns that reference it, then drop the old type.
    op.execute("ALTER TYPE failurecategory RENAME TO failurecategory_old")
    op.execute("""
        CREATE TYPE failurecategory AS ENUM (
            'SCHEMA_VIOLATION', 'HALLUCINATION_SIGNAL', 'MISSING_REQUIRED_FIELD',
            'SAFETY_FLAG', 'TIMEOUT', 'PROVIDER_ERROR', 'HUMAN_ESCALATED',
            'VALIDATION_FAILURE', 'INPUT_VALIDATION_ERROR'
        )
    """)
    op.execute(
        "ALTER TABLE llm_calls ALTER COLUMN failure_category TYPE failurecategory "
        "USING failure_category::text::failurecategory"
    )
    op.execute(
        "ALTER TABLE escalation_records ALTER COLUMN failure_category TYPE failurecategory "
        "USING failure_category::text::failurecategory"
    )
    op.execute("DROP TYPE failurecategory_old")
