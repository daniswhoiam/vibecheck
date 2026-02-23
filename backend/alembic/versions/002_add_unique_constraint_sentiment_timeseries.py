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
    """No-op: sentiment_timeseries was dropped in 006_reset_schema.

    Originally this added a unique constraint to sentiment_timeseries,
    but that table no longer exists after 006_reset_schema. When the DB
    is migrated fresh (from revision 001 through 009_merge_heads),
    006_reset_schema runs before this migration in the new-schema branch,
    so the table is already gone by the time this runs.
    """
    pass


def downgrade() -> None:
    """No-op downgrade."""
    pass
