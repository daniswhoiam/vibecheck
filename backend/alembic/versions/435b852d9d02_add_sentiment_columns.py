"""add sentiment columns to entities

Revision ID: 435b852d9d02
Revises: 001
Create Date: 2026-02-05 11:00:00.000000

NOTE: This stub migration restores the missing revision 435b852d9d02
to fix the Alembic revision chain. The original migration added sentiment
columns that were later superseded by 006_reset_schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '435b852d9d02'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Stub: original migration added sentiment columns (later superseded by 006_reset_schema)."""
    pass


def downgrade() -> None:
    """Stub: no-op downgrade."""
    pass
