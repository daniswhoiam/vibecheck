"""Database session management for async SQLAlchemy operations.

Provides async engine, session factory, and FastAPI dependency for database access.
"""
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Get database URL from environment with default for local development
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://vibecheck:password@localhost:5432/vibecheck"
)

# Get SQL echo setting from environment
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

# Create async engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=SQL_ECHO,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
)

# Create async session factory
# CRITICAL: expire_on_commit=False prevents post-commit attribute access
# from triggering implicit database queries in async context
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session injection.

    Yields an async session and handles cleanup automatically.

    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
