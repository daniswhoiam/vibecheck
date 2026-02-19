"""add unique constraint to sentiment_timeseries for upsert

Revision ID: 002
Revises: 6d279f8e2869
Create Date: 2026-02-05 14:20:00.000000

This migration adds a unique constraint on (entity_id, timestamp, period)
to enable proper upsert behavior using INSERT ... ON CONFLICT DO NOTHING.
This prevents duplicate time-series entries for the same entity, timestamp,
and aggregation period.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '67a003713f58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint to sentiment_timeseries table."""

    # Create unique constraint on (entity_id, timestamp, period)
    # This enables proper upsert behavior in sentiment_service.py
    op.create_unique_constraint(
        'uq_sentiment_timeseries_entity_timestamp_period',
        'sentiment_timeseries',
        ['entity_id', 'timestamp', 'period']
    )


def downgrade() -> None:
    """Remove unique constraint from sentiment_timeseries table."""

    op.drop_constraint(
        'uq_sentiment_timeseries_entity_timestamp_period',
        'sentiment_timeseries',
        type_='unique'
    )
