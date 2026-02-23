"""merge legacy branch (002) and new schema branch (008)

Revision ID: 009_merge_heads
Revises: 002, 008_create_sentiment_rollup_table
Create Date: 2026-02-23

This migration merges the legacy sentiment_timeseries branch (which ends at
revision 002) with the new schema branch (which ends at 008_create_sentiment_rollup_table).

The legacy branch created/modified sentiment_timeseries tables that were then
dropped by 006_reset_schema. Both branches share the common ancestor 67a003713f58.

This merge head enables `alembic upgrade head` to work when the database is at
either `002` or `008_create_sentiment_rollup_table`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_merge_heads'
down_revision: Union[tuple, None] = ('002', '008_create_sentiment_rollup_table')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration: unifies legacy (002) and new-schema (008) branches.

    Also creates scheduler_execution_log table, which was previously created
    directly in the DB without a migration (the 67a003713f58 migration was
    misnamed — it only modified a sentiment_timeseries index).
    """
    op.create_table(
        'scheduler_execution_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('execution_id', sa.String(36), nullable=False),
        sa.Column('job_name', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scheduler_execution_log_execution_id', 'scheduler_execution_log', ['execution_id'])
    op.create_index('ix_scheduler_execution_log_job_name', 'scheduler_execution_log', ['job_name'])


def downgrade() -> None:
    """Drop scheduler_execution_log and unmerge branches."""
    op.drop_index('ix_scheduler_execution_log_job_name', table_name='scheduler_execution_log')
    op.drop_index('ix_scheduler_execution_log_execution_id', table_name='scheduler_execution_log')
    op.drop_table('scheduler_execution_log')
