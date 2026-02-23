"""Create sentiment_rollup table for daily per-entity sentiment aggregation.

Revision ID: 008_create_sentiment_rollup_table
Revises: 007_add_sentiment_columns_to_posts
Create Date: 2026-02-23
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '008_create_sentiment_rollup_table'
down_revision: Union[str, Sequence[str], None] = '007_add_sentiment_columns_to_posts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sentiment_rollup',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('rollup_date', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('sentiment_mean', sa.Float(), nullable=True),
        sa.Column('post_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source_breakdown', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_id', 'rollup_date', name='uq_sentiment_rollup_entity_date'),
    )
    op.create_index('ix_sentiment_rollup_entity_date', 'sentiment_rollup', ['entity_id', 'rollup_date'])
    op.create_index('ix_sentiment_rollup_entity_id', 'sentiment_rollup', ['entity_id'])


def downgrade() -> None:
    op.drop_index('ix_sentiment_rollup_entity_id', table_name='sentiment_rollup')
    op.drop_index('ix_sentiment_rollup_entity_date', table_name='sentiment_rollup')
    op.drop_table('sentiment_rollup')
