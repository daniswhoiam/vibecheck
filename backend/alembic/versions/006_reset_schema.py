"""Reset schema: drop old tables, create posts hypertable + aspect_sentiments + post_entity_mentions.

Revision ID: 006_reset_schema
Revises: 67a003713f58
Create Date: 2026-02-19

IMPORTANT: Requires timescale/timescaledb-ha:pg16-latest Docker image.
If running against postgres:16-alpine, the create_hypertable call will fail.
To upgrade: docker-compose down -v && docker-compose up -d
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '006_reset_schema'
down_revision: Union[str, Sequence[str], None] = '67a003713f58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === 0. Widen alembic_version.version_num to accommodate descriptive revision IDs ===
    # Default is varchar(32); revision IDs like '007_add_sentiment_columns_to_posts' (35 chars)
    # exceed this limit. Widen to varchar(64) before applying subsequent migrations.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")

    # === 1. Drop old tables (FK-safe order: children before parents) ===
    op.execute("DROP TABLE IF EXISTS sentiment_timeseries CASCADE")
    op.execute("DROP TABLE IF EXISTS articles CASCADE")
    op.execute("DROP TABLE IF EXISTS entities CASCADE")

    # === 2. Create required extensions ===
    # timescaledb must come before vector in case of dependency ordering
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # === 3. Recreate entities table (empty — re-seeded in a later phase) ===
    op.create_table(
        'entities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint('name', name='uq_entities_name'),
    )

    # === 4. Create posts table ===
    # NOTE: TimescaleDB requires ALL unique constraints to include the partitioning column
    # (published_at). We use a regular index on content_hash (not unique constraint) and
    # handle deduplication at the application layer via SELECT-before-INSERT or
    # ON CONFLICT DO NOTHING on source+external_id+published_at.
    op.create_table(
        'posts',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('published_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', 'published_at'),
        # TimescaleDB unique constraints MUST include the partition key (published_at)
        sa.UniqueConstraint('source', 'external_id', 'published_at', name='uq_posts_source_external_id'),
    )

    # === 5. Convert posts to TimescaleDB hypertable (partition by published_at) ===
    op.execute(
        "SELECT create_hypertable('posts', 'published_at', if_not_exists => TRUE)"
    )

    # === 6. Useful indexes on posts ===
    # content_hash uses a regular index (not unique) — TimescaleDB unique constraints
    # require the partition key, but content_hash dedup uses app-level checking.
    op.create_index('ix_posts_content_hash', 'posts', ['content_hash'])
    op.create_index('ix_posts_source', 'posts', ['source'])
    op.create_index('ix_posts_published_at', 'posts', ['published_at'])

    # === 7. Create post_entity_mentions (many-to-many junction) ===
    # NOTE: No FK from post_id -> posts.id. TimescaleDB does not allow foreign key
    # constraints that reference a hypertable (posts). Referential integrity for
    # post_id is enforced at the application layer (Phase 6 storage service).
    # The entity_id FK to entities is safe because entities is NOT a hypertable.
    op.create_table(
        'post_entity_mentions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('post_id', 'entity_id', name='uq_post_entity_mentions'),
    )
    op.create_index('ix_post_entity_mentions_entity_id', 'post_entity_mentions', ['entity_id'])
    op.create_index('ix_post_entity_mentions_post_id', 'post_entity_mentions', ['post_id'])

    # === 8. Create aspect_sentiments ===
    # NOTE: No FK from post_id -> posts.id. TimescaleDB does not allow foreign key
    # constraints that reference a hypertable (posts). Referential integrity for
    # post_id is enforced at the application layer (Phase 6 storage service).
    # The entity_id FK to entities is safe because entities is NOT a hypertable.
    op.create_table(
        'aspect_sentiments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('aspect', sa.String(50), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.CheckConstraint('score >= -1.0 AND score <= 1.0', name='ck_aspect_sentiments_score'),
        sa.UniqueConstraint('post_id', 'entity_id', 'aspect', name='uq_aspect_sentiments'),
    )
    op.create_index('ix_aspect_sentiments_entity_aspect', 'aspect_sentiments', ['entity_id', 'aspect'])
    op.create_index('ix_aspect_sentiments_post_id', 'aspect_sentiments', ['post_id'])


def downgrade() -> None:
    """Downgrade drops the new schema. Cannot restore old data (fresh start decision)."""
    # op.drop_table() does not support if_exists parameter — use op.execute() for conditional drops
    op.execute("DROP TABLE IF EXISTS aspect_sentiments")
    op.execute("DROP TABLE IF EXISTS post_entity_mentions")
    op.execute("DROP TABLE IF EXISTS posts CASCADE")
    op.execute("DROP TABLE IF EXISTS entities")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE")
    # Note: unique constraint uq_posts_content_hash was dropped in favour of ix_posts_content_hash
