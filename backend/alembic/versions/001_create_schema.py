"""Create initial schema with entities, articles, and sentiment_timeseries tables.

Revision ID: 001
Revises:
Create Date: 2026-02-05 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create entities, articles, and sentiment_timeseries tables."""

    # Create entities table
    op.create_table(
        'entities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create articles table
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=True),
        sa.Column('published_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            'sentiment_score >= -1 AND sentiment_score <= 1',
            name='ck_article_sentiment_score_range'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
        sa.UniqueConstraint('url')
    )
    op.create_index('ix_articles_external_id', 'articles', ['external_id'])
    op.create_index('ix_articles_published_at', 'articles', ['published_at'])

    # Create sentiment_timeseries table
    op.create_table(
        'sentiment_timeseries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('period', sa.String(length=10), nullable=False),
        sa.Column('sentiment_mean', sa.Float(), nullable=True),
        sa.Column('sentiment_min', sa.Float(), nullable=True),
        sa.Column('sentiment_max', sa.Float(), nullable=True),
        sa.Column('sentiment_std', sa.Float(), nullable=True),
        sa.Column('article_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            'sentiment_mean >= -1 AND sentiment_mean <= 1',
            name='ck_sentiment_timeseries_mean_range'
        ),
        sa.CheckConstraint(
            'sentiment_min >= -1 AND sentiment_min <= 1',
            name='ck_sentiment_timeseries_min_range'
        ),
        sa.CheckConstraint(
            'sentiment_max >= -1 AND sentiment_max <= 1',
            name='ck_sentiment_timeseries_max_range'
        ),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sentiment_timeseries_entity_id', 'sentiment_timeseries', ['entity_id'])
    op.create_index('ix_sentiment_timeseries_timestamp', 'sentiment_timeseries', ['timestamp'])

    # Create composite index on (entity_id, timestamp DESC) for efficient time-series queries
    op.create_index(
        'ix_sentiment_timeseries_entity_timestamp',
        'sentiment_timeseries',
        ['entity_id', sa.text('timestamp DESC')],
        postgresql_ops={'timestamp': 'DESC'}
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index('ix_sentiment_timeseries_entity_timestamp', table_name='sentiment_timeseries')
    op.drop_index('ix_sentiment_timeseries_timestamp', table_name='sentiment_timeseries')
    op.drop_index('ix_sentiment_timeseries_entity_id', table_name='sentiment_timeseries')
    op.drop_table('sentiment_timeseries')

    op.drop_index('ix_articles_published_at', table_name='articles')
    op.drop_index('ix_articles_external_id', table_name='articles')
    op.drop_table('articles')

    op.drop_table('entities')
