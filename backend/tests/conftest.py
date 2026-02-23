"""Shared fixtures for Phase 8 (Tier 2 LLM aspect extraction) tests.

Provides: mock_llm_provider, low_confidence_post, high_confidence_post,
sample_aspect_data fixtures used across test modules.
"""
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_llm_provider():
    """AsyncMock LLM provider that returns valid aspect dict for any input.

    Returns a dict keyed by entity name, each value is a dict of aspect -> score.
    All 7 aspects are included with neutral scores (0.0) by default.
    """
    provider = AsyncMock()
    provider.extract_aspects = AsyncMock(
        return_value={
            "Claude": {
                "performance": 0.5,
                "cost": -0.3,
                "reliability": 0.4,
                "ux": 0.6,
                "speed": 0.7,
                "code_quality": 0.8,
                "context_window": 0.2,
            }
        }
    )
    return provider


@pytest.fixture
def low_confidence_post():
    """Sample post with low Tier 1 confidence — should be routed to Tier 2.

    sentiment_score=0.4 is below the 0.6 threshold. sentiment_label is set
    (post has been scored by Tier 1), so it qualifies for Tier 2 routing.
    """
    return {
        "id": 101,
        "title": "My experience with Claude vs GPT-4o",
        "body": (
            "I've been using Claude for a few weeks. The performance is decent "
            "but the cost is a bit high. Context window is impressive though."
        ),
        "sentiment_label": "Neutral",
        "sentiment_score": 0.4,
        "source": "hn",
    }


@pytest.fixture
def high_confidence_post():
    """Sample post with high Tier 1 confidence — should NOT be routed to Tier 2.

    sentiment_score=0.9 is above the 0.6 threshold, so Tier 2 is skipped.
    """
    return {
        "id": 102,
        "title": "Claude is absolutely amazing!",
        "body": "Claude is by far the best AI coding assistant I have ever used.",
        "sentiment_label": "Positive",
        "sentiment_score": 0.9,
        "source": "reddit",
    }


@pytest.fixture
def sample_aspect_data():
    """List of AspectSentiment-compatible dicts for API endpoint tests.

    Represents stored aspect sentiments for entity_id=1 (Claude) linked to
    two posts. Used to seed test DB or mock query results.
    """
    return [
        {"post_id": 101, "entity_id": 1, "aspect": "performance", "score": 0.5},
        {"post_id": 101, "entity_id": 1, "aspect": "cost", "score": -0.3},
        {"post_id": 101, "entity_id": 1, "aspect": "reliability", "score": 0.4},
        {"post_id": 101, "entity_id": 1, "aspect": "ux", "score": 0.6},
        {"post_id": 101, "entity_id": 1, "aspect": "speed", "score": 0.7},
        {"post_id": 101, "entity_id": 1, "aspect": "code_quality", "score": 0.8},
        {"post_id": 101, "entity_id": 1, "aspect": "context_window", "score": 0.2},
        {"post_id": 102, "entity_id": 1, "aspect": "performance", "score": 0.9},
        {"post_id": 102, "entity_id": 1, "aspect": "cost", "score": 0.1},
        {"post_id": 102, "entity_id": 1, "aspect": "reliability", "score": 0.8},
        {"post_id": 102, "entity_id": 1, "aspect": "ux", "score": 0.7},
        {"post_id": 102, "entity_id": 1, "aspect": "speed", "score": 0.6},
        {"post_id": 102, "entity_id": 1, "aspect": "code_quality", "score": 0.9},
        {"post_id": 102, "entity_id": 1, "aspect": "context_window", "score": 0.5},
    ]
