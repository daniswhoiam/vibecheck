"""SQLAlchemy declarative base for async ORM models.

AsyncAttrs mixin enables lazy-loaded relationships to work correctly
with async sessions by preventing implicit synchronous queries.
"""
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models.

    Inherits from AsyncAttrs to enable async-compatible lazy loading
    and DeclarativeBase for SQLAlchemy 2.0 declarative mapping.
    """
    pass
