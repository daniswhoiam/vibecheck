"""Add sentiment_label and sentiment_score columns to posts table.

Revision ID: 007_add_sentiment_columns_to_posts
Revises: 006_reset_schema
Create Date: 2026-02-23
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '007_add_sentiment_columns_to_posts'
down_revision: Union[str, Sequence[str], None] = '006_reset_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('sentiment_label', sa.String(20), nullable=True))
    op.add_column('posts', sa.Column('sentiment_score', sa.Float(), nullable=True))
    op.create_index('ix_posts_sentiment_label', 'posts', ['sentiment_label'])


def downgrade() -> None:
    op.drop_index('ix_posts_sentiment_label', table_name='posts')
    op.drop_column('posts', 'sentiment_score')
    op.drop_column('posts', 'sentiment_label')
