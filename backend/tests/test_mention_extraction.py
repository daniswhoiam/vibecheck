"""Tests for MentionExtractor service — TDD RED phase.

Tests written before mention_service.py is created. Imports will fail
(ImportError/ModuleNotFoundError) until mention_service.py is implemented.

Test coverage:
- MentionExtractor.extract_mentions(): word boundary matching, case insensitivity,
  multiple entities, empty/None text, uninitialized state guard
- extract_and_save_mentions(): DB insert, zero-mention short-circuit, ON CONFLICT
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from pipeline.services.mention_service import MentionExtractor, extract_and_save_mentions


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def entity_map():
    """Base entity map for direct injection into MentionExtractor."""
    return {"Claude": 1, "GPT-4o": 2, "Cursor": 3}


@pytest.fixture
def extractor(entity_map):
    """MentionExtractor with entity_map pre-loaded (bypasses DB load for unit tests)."""
    e = MentionExtractor()
    e._entity_map = entity_map  # Inject directly — avoids needing a live database
    return e


# ---------------------------------------------------------------------------
# Class TestMentionExtractorExtractMentions
# ---------------------------------------------------------------------------

class TestMentionExtractorExtractMentions:
    """Unit tests for MentionExtractor.extract_mentions() — pure logic, no DB."""

    def test_single_entity_match(self, extractor):
        """Single entity match returns the correct entity ID set."""
        entity_map = {"Claude": 1}
        extractor._entity_map = entity_map
        result = extractor.extract_mentions("I use Claude daily")
        assert result == {1}

    def test_word_boundary_prevents_false_positive(self, extractor):
        """'AI' inside 'trained' should NOT match the entity 'AI'."""
        entity_map = {"AI": 99}
        extractor._entity_map = entity_map
        # "trained" contains "ai" as substring — must NOT match
        result = extractor.extract_mentions("he trained his model")
        assert result == set()

    def test_case_insensitive_match(self, extractor):
        """Entity matching is case-insensitive — 'CLAUDE' matches 'Claude' entity."""
        entity_map = {"Claude": 1}
        extractor._entity_map = entity_map
        result = extractor.extract_mentions("using CLAUDE for tasks")
        assert result == {1}

    def test_multiple_entities_in_text(self, extractor):
        """Multiple entities in text returns all matching entity IDs."""
        entity_map = {"Claude": 1, "GPT-4o": 2}
        extractor._entity_map = entity_map
        result = extractor.extract_mentions("Claude vs GPT-4o comparison")
        assert result == {1, 2}

    def test_entity_not_present(self, extractor):
        """Text with no matching entity returns an empty set."""
        entity_map = {"Claude": 1}
        extractor._entity_map = entity_map
        result = extractor.extract_mentions("I prefer to work alone")
        assert result == set()

    def test_empty_text_returns_empty_set(self, extractor):
        """Empty string returns an empty set without error."""
        result = extractor.extract_mentions("")
        assert result == set()

    def test_none_text_returns_empty_set(self, extractor):
        """None input returns an empty set — guard against None from DB rows."""
        result = extractor.extract_mentions(None)
        assert result == set()

    def test_not_initialized_raises_runtime_error(self):
        """Calling extract_mentions() before load_entities() raises RuntimeError."""
        e = MentionExtractor()
        # _entity_map is None by default — not initialized
        with pytest.raises(RuntimeError, match="load_entities"):
            e.extract_mentions("some text")


# ---------------------------------------------------------------------------
# Class TestExtractAndSaveMentions
# ---------------------------------------------------------------------------

class TestExtractAndSaveMentions:
    """Tests for extract_and_save_mentions() — tests DB interaction via mocks."""

    @pytest.mark.asyncio
    async def test_inserts_mention_rows_and_returns_count(self, extractor):
        """When entities are found, rows are inserted and count is returned."""
        # Set up extractor to find entity ID 1 in the text
        extractor._entity_map = {"Claude": 1, "GPT-4o": 2}

        # Mock session: execute called twice (insert + count query)
        mock_session = AsyncMock()

        # First execute: the pg_insert ON CONFLICT statement
        insert_result = MagicMock()
        # Second execute: the count SELECT query
        count_result = MagicMock()
        count_result.all = MagicMock(return_value=[MagicMock(), MagicMock()])  # 2 rows

        mock_session.execute = AsyncMock(side_effect=[insert_result, count_result])
        mock_session.commit = AsyncMock()

        result = await extract_and_save_mentions(
            session=mock_session,
            post_id=42,
            text="I use Claude and GPT-4o daily",
            extractor=extractor,
        )

        assert result == 2
        assert mock_session.execute.call_count == 2  # insert + count
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_entities_found_returns_zero(self, extractor):
        """When no entities are found in text, function returns 0 without DB insert."""
        extractor._entity_map = {"Claude": 1}

        mock_session = AsyncMock()

        result = await extract_and_save_mentions(
            session=mock_session,
            post_id=99,
            text="I prefer to work alone on this project",
            extractor=extractor,
        )

        assert result == 0
        # No DB calls should be made when no entities are found
        mock_session.execute.assert_not_called()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_on_conflict_do_nothing(self, extractor):
        """The INSERT statement uses ON CONFLICT DO NOTHING for idempotency."""
        extractor._entity_map = {"Claude": 1}

        mock_session = AsyncMock()
        insert_result = MagicMock()
        count_result = MagicMock()
        count_result.all = MagicMock(return_value=[MagicMock()])

        mock_session.execute = AsyncMock(side_effect=[insert_result, count_result])
        mock_session.commit = AsyncMock()

        # Patch pg_insert to capture the statement being built
        with patch("pipeline.services.mention_service.pg_insert") as mock_pg_insert:
            # Set up mock chain: pg_insert(...).values([...]).on_conflict_do_nothing()
            mock_insert_obj = MagicMock()
            mock_values_obj = MagicMock()
            mock_conflict_obj = MagicMock()

            mock_pg_insert.return_value = mock_insert_obj
            mock_insert_obj.values.return_value = mock_values_obj
            mock_values_obj.on_conflict_do_nothing.return_value = mock_conflict_obj

            await extract_and_save_mentions(
                session=mock_session,
                post_id=10,
                text="Claude is great for coding",
                extractor=extractor,
            )

            # Verify ON CONFLICT DO NOTHING was called
            mock_values_obj.on_conflict_do_nothing.assert_called_once()
