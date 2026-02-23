"""SQLAlchemy ORM models for VibeCheck multi-source sentiment pipeline.

Schema designed for TimescaleDB hypertables (posts) and pgvector embeddings.
All timestamps use TIMESTAMP WITH TIME ZONE stored in UTC.
"""
import numpy as np
from datetime import datetime
from sqlalchemy import (
    BigInteger, String, Text, Integer, Float, TIMESTAMP,
    CheckConstraint, ForeignKey, Index, JSON, func, Identity, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from db.base import Base


class Entity(Base):
    """AI models and tools tracked for sentiment analysis."""
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    post_mentions: Mapped[list["PostEntityMention"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    aspect_sentiments: Mapped[list["AspectSentiment"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    sentiment_rollups: Mapped[list["SentimentRollup"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class Post(Base):
    """Social media posts and articles from tracked sources.

    Partitioned as a TimescaleDB hypertable on published_at for efficient
    time-range queries. Stores full post content for aspect-level analysis.
    """
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NOTE: TimescaleDB requires unique constraints to include the partition key (published_at).
    # content_hash uses a regular index (not unique) — dedup handled at application level.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    post_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    embedding: Mapped[np.ndarray | None] = mapped_column(Vector(384), nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True, primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    sentiment_label: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships — viewonly because post_id has no DB-level FK
    # (TimescaleDB does not allow FK constraints referencing a hypertable)
    # viewonly=True: cascade and back-population require a real FK; use these for reads only.
    entity_mentions: Mapped[list["PostEntityMention"]] = relationship(
        primaryjoin="Post.id == foreign(PostEntityMention.post_id)",
        viewonly=True,
        foreign_keys="[PostEntityMention.post_id]",
    )
    aspect_sentiments: Mapped[list["AspectSentiment"]] = relationship(
        primaryjoin="Post.id == foreign(AspectSentiment.post_id)",
        viewonly=True,
        foreign_keys="[AspectSentiment.post_id]",
    )

    __table_args__ = (
        # TimescaleDB: unique constraints must include partition key published_at
        UniqueConstraint('source', 'external_id', 'published_at', name='uq_posts_source_external_id'),
    )


class PostEntityMention(Base):
    """Many-to-many junction: which entities are mentioned in which posts."""
    __tablename__ = "post_entity_mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # NOTE: No ForeignKey to posts.id — TimescaleDB does not allow FK constraints that
    # reference a hypertable. Referential integrity is enforced at the application layer.
    post_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    # viewonly relationship to Post — no DB-level FK (TimescaleDB hypertable constraint)
    post: Mapped["Post"] = relationship(
        primaryjoin="PostEntityMention.post_id == foreign(Post.id)",
        foreign_keys="[PostEntityMention.post_id]",
        viewonly=True,
    )
    entity: Mapped["Entity"] = relationship(back_populates="post_mentions")

    __table_args__ = (
        UniqueConstraint('post_id', 'entity_id', name='uq_post_entity_mentions'),
    )


class AspectSentiment(Base):
    """Aspect-level sentiment score for a specific entity in a post.

    Aspects: performance, cost, reliability, ux, speed, code_quality, context_window
    Score range: -1.0 (very negative) to 1.0 (very positive).
    Application validates aspect values against VALID_ASPECTS constant.
    """
    __tablename__ = "aspect_sentiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # NOTE: No ForeignKey to posts.id — TimescaleDB does not allow FK constraints that
    # reference a hypertable. Referential integrity is enforced at the application layer.
    post_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    aspect: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    # viewonly relationship to Post — no DB-level FK (TimescaleDB hypertable constraint)
    post: Mapped["Post"] = relationship(
        primaryjoin="AspectSentiment.post_id == foreign(Post.id)",
        foreign_keys="[AspectSentiment.post_id]",
        viewonly=True,
    )
    entity: Mapped["Entity"] = relationship(back_populates="aspect_sentiments")

    __table_args__ = (
        CheckConstraint('score >= -1.0 AND score <= 1.0', name='ck_aspect_sentiments_score'),
        UniqueConstraint('post_id', 'entity_id', 'aspect', name='uq_aspect_sentiments'),
        Index('ix_aspect_sentiments_entity_aspect', 'entity_id', 'aspect'),
    )


class SentimentRollup(Base):
    """Daily sentiment rollup with per-source breakdown.

    One row per (entity, day). Incrementally recomputed for the current UTC day
    on each aggregation job run. Past days are immutable once written.

    source_breakdown JSON structure:
        {"hn": {"mean": 0.4, "count": 12}, "reddit": {"mean": -0.1, "count": 8}, ...}
    """
    __tablename__ = "sentiment_rollup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rollup_date: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    sentiment_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    entity: Mapped["Entity"] = relationship(back_populates="sentiment_rollups")

    __table_args__ = (
        UniqueConstraint('entity_id', 'rollup_date', name='uq_sentiment_rollup_entity_date'),
        Index('ix_sentiment_rollup_entity_date', 'entity_id', 'rollup_date'),
    )


class SchedulerExecutionLog(Base):
    """Audit trail for scheduled job executions."""
    __tablename__ = "scheduler_execution_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    job_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
