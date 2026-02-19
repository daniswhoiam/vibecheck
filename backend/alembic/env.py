import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Import Base and all models for autogenerate support
from db.base import Base
from db.models import Entity, Post, PostEntityMention, AspectSentiment, SchedulerExecutionLog
import pgvector.sqlalchemy

# Get DATABASE_URL from environment (same as used by the application)
# This ensures migrations use the same database as the running app
database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://vibecheck:password@postgres:5432/vibecheck")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target_metadata to Base.metadata for autogenerate support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


# TimescaleDB internal schemas — exclude from autogenerate to prevent false drift
TIMESCALE_SCHEMAS = {
    '_timescaledb_cache',
    '_timescaledb_catalog',
    '_timescaledb_config',
    '_timescaledb_internal',
    'timescaledb_information',
}


def include_object(object, name, type_, reflected, compare_to):
    """Filter out TimescaleDB internals and auto-created indexes from autogenerate."""
    if type_ == "schema" and name in TIMESCALE_SCHEMAS:
        return False
    # Exclude TimescaleDB auto-created hypertable index on published_at
    if type_ == "index" and name == "posts_published_at_idx":
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async support.

    In this scenario we need to create an async Engine
    and associate a connection with the context.

    """
    connectable = create_async_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection):
    """Helper function to run migrations synchronously within async context."""
    # Register vector type to prevent alembic check from detecting false drift
    connection.dialect.ischema_names['vector'] = pgvector.sqlalchemy.Vector
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
