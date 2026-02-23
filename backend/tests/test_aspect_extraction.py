"""Tests for Tier 2 LLM aspect extraction job (Phase 8).

Tests cover:
- Routing logic: posts with confidence < 0.6 are routed to Tier 2
- Routing logic: posts with confidence >= 0.6 are NOT routed
- Idempotency: posts with existing AspectSentiment rows are NOT reprocessed
- Posts not yet scored (sentiment_label=None) are NOT routed
- Successful extraction writes AspectSentiment rows per entity per aspect
- All 7 aspects stored per entity (even neutral 0.0 ones)
- Unmatched LLM entity names (not in PostEntityMention) are skipped
- Stats dict returned: {routed, extracted, errors}

RED phase: All tests fail with ImportError (modules not yet created).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# These imports WILL fail (RED phase) — module does not exist yet.
# Implementation in plan 03 will create it.
from pipeline.jobs.extract_aspects import run_extract_aspects  # noqa: F401

from utils.constants import VALID_ASPECTS  # noqa: F401 — already exists


class TestTier2RoutingLogic:
    """Tests for which posts are routed to Tier 2 LLM processing."""

    @pytest.mark.asyncio
    async def test_low_confidence_post_is_routed_to_tier2(
        self, mock_llm_provider
    ):
        """Post with sentiment_score=0.5 (< 0.6) and no existing AspectSentiment rows → Tier 2."""
        mock_session = AsyncMock()

        # Simulate query returning one low-confidence post with no existing aspects
        mock_post_row = MagicMock()
        mock_post_row.id = 101
        mock_post_row.title = "Claude review"
        mock_post_row.body = "Claude is good but expensive"
        mock_post_row.sentiment_score = 0.5
        mock_post_row.sentiment_label = "Neutral"

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[mock_post_row])

        # Simulate mention query
        mock_mention_row = MagicMock()
        mock_mention_row.entity_id = 1
        mock_mention_row.name = "Claude"
        mock_mention_result = MagicMock()
        mock_mention_result.all = MagicMock(return_value=[mock_mention_row])

        mock_session.execute = AsyncMock(
            side_effect=[mock_result, mock_mention_result]
        )

        with patch(
            "pipeline.jobs.extract_aspects.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            stats = await run_extract_aspects(mock_session)

        assert stats["routed"] >= 1

    @pytest.mark.asyncio
    async def test_high_confidence_post_is_not_routed(self, mock_llm_provider):
        """Post with sentiment_score=0.8 (>= 0.6) is NOT routed to Tier 2."""
        mock_session = AsyncMock()

        # Query returns no posts (high confidence filtered out at DB layer)
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "pipeline.jobs.extract_aspects.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            stats = await run_extract_aspects(mock_session)

        assert stats["routed"] == 0
        assert stats["extracted"] == 0
        # LLM provider should not have been called for high-confidence post
        mock_llm_provider.extract_aspects.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_with_existing_aspects_is_not_reprocessed(
        self, mock_llm_provider
    ):
        """Post with sentiment_score=0.5 that already has AspectSentiment rows → skipped (idempotent)."""
        mock_session = AsyncMock()

        # Query returns no posts because NOT EXISTS filter excludes already-processed posts
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "pipeline.jobs.extract_aspects.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            stats = await run_extract_aspects(mock_session)

        assert stats["extracted"] == 0
        mock_llm_provider.extract_aspects.assert_not_called()

    @pytest.mark.asyncio
    async def test_unscored_post_is_not_routed(self, mock_llm_provider):
        """Post with sentiment_label=None is NOT routed (not yet scored by Tier 1)."""
        mock_session = AsyncMock()

        # Query returns no posts because sentiment_label IS NOT NULL filter excludes unscored
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "pipeline.jobs.extract_aspects.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            stats = await run_extract_aspects(mock_session)

        assert stats["routed"] == 0
        mock_llm_provider.extract_aspects.assert_not_called()


class TestAspectStorage:
    """Tests for AspectSentiment storage behavior after extraction."""

    @pytest.mark.asyncio
    async def test_successful_extraction_writes_aspect_rows(
        self, mock_llm_provider
    ):
        """Successful extraction writes AspectSentiment rows with (post_id, entity_id, aspect, score)."""
        mock_session = AsyncMock()

        mock_post_row = MagicMock()
        mock_post_row.id = 101
        mock_post_row.title = "Claude review"
        mock_post_row.body = "Claude is incredible for code"
        mock_post_row.sentiment_score = 0.4
        mock_post_row.sentiment_label = "Positive"

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[mock_post_row])

        mock_mention_row = MagicMock()
        mock_mention_row.entity_id = 1
        mock_mention_row.name = "Claude"
        mock_mention_result = MagicMock()
        mock_mention_result.all = MagicMock(return_value=[mock_mention_row])

        mock_session.execute = AsyncMock(
            side_effect=[mock_result, mock_mention_result]
        )

        with patch(
            "pipeline.jobs.extract_aspects.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            stats = await run_extract_aspects(mock_session)

        assert stats["extracted"] >= 1
        # session.add() or session.execute() for INSERT should have been called
        assert mock_session.commit.called or mock_session.flush.called

    @pytest.mark.asyncio
    async def test_all_7_aspects_stored_per_entity(self, mock_llm_provider):
        """All 7 aspects stored per entity in routed post (even if some are neutral 0.0)."""
        mock_session = AsyncMock()

        # LLM returns all 7 aspects
        mock_llm_provider.extract_aspects = AsyncMock(
            return_value={
                "Claude": {
                    "performance": 0.5,
                    "cost": 0.0,
                    "reliability": 0.0,
                    "ux": 0.0,
                    "speed": 0.0,
                    "code_quality": 0.8,
                    "context_window": 0.0,
                }
            }
        )

        mock_post_row = MagicMock()
        mock_post_row.id = 101
        mock_post_row.title = "Claude review"
        mock_post_row.body = "Claude is decent"
        mock_post_row.sentiment_score = 0.3
        mock_post_row.sentiment_label = "Neutral"

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[mock_post_row])

        mock_mention_row = MagicMock()
        mock_mention_row.entity_id = 1
        mock_mention_row.name = "Claude"
        mock_mention_result = MagicMock()
        mock_mention_result.all = MagicMock(return_value=[mock_mention_row])

        mock_session.execute = AsyncMock(
            side_effect=[mock_result, mock_mention_result]
        )

        added_objects = []
        mock_session.add = MagicMock(side_effect=added_objects.append)

        with patch(
            "pipeline.jobs.extract_aspects.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            stats = await run_extract_aspects(mock_session)

        # 7 aspects for 1 entity = 7 AspectSentiment rows added
        assert len(added_objects) == len(VALID_ASPECTS)

    @pytest.mark.asyncio
    async def test_unmatched_llm_entity_names_are_skipped(
        self, mock_llm_provider
    ):
        """LLM entity name not matching PostEntityMention by name lookup → skipped."""
        mock_session = AsyncMock()

        # LLM returns an entity name not in PostEntityMention
        mock_llm_provider.extract_aspects = AsyncMock(
            return_value={
                "GPT-4o": {  # Not in post's entity mentions
                    "performance": 0.9,
                    "cost": 0.5,
                    "reliability": 0.8,
                    "ux": 0.7,
                    "speed": 0.6,
                    "code_quality": 0.9,
                    "context_window": 0.8,
                }
            }
        )

        mock_post_row = MagicMock()
        mock_post_row.id = 101
        mock_post_row.title = "Claude review"
        mock_post_row.body = "Claude is decent"
        mock_post_row.sentiment_score = 0.3
        mock_post_row.sentiment_label = "Neutral"

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[mock_post_row])

        # Post only mentions Claude, but LLM returned GPT-4o
        mock_mention_row = MagicMock()
        mock_mention_row.entity_id = 1
        mock_mention_row.name = "Claude"
        mock_mention_result = MagicMock()
        mock_mention_result.all = MagicMock(return_value=[mock_mention_row])

        mock_session.execute = AsyncMock(
            side_effect=[mock_result, mock_mention_result]
        )

        added_objects = []
        mock_session.add = MagicMock(side_effect=added_objects.append)

        with patch(
            "pipeline.jobs.extract_aspects.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            await run_extract_aspects(mock_session)

        # GPT-4o not in PostEntityMentions → no rows added
        assert len(added_objects) == 0


class TestRunExtractAspectsStats:
    """Tests for the stats dict returned by run_extract_aspects()."""

    @pytest.mark.asyncio
    async def test_stats_dict_has_correct_keys(self, mock_llm_provider):
        """Stats dict returned by run_extract_aspects has {routed, extracted, errors} keys."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "pipeline.jobs.extract_aspects.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            stats = await run_extract_aspects(mock_session)

        assert "routed" in stats
        assert "extracted" in stats
        assert "errors" in stats

    @pytest.mark.asyncio
    async def test_empty_run_returns_zero_stats(self, mock_llm_provider):
        """When no posts are eligible, stats are all zeros."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "pipeline.jobs.extract_aspects.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            stats = await run_extract_aspects(mock_session)

        assert stats["routed"] == 0
        assert stats["extracted"] == 0
        assert stats["errors"] == 0
