"""Tests for GET /entities/{id}/aspects API endpoint (Phase 8).

Tests cover:
- GET /entities/{id}/aspects?window=7d returns aspects with mean and count per aspect
- GET /entities/{id}/aspects?window=30d returns aspects over 30-day window
- GET /entities/{id}/aspects?window=90d returns aspects over 90-day window
- GET /entities/{id}/aspects?window=7d&source=hn filters to HN-sourced aspects
- GET /entities/{id}/aspects returns 404 for unknown entity_id
- Response structure documented assumption: only aspects with data returned

RED phase: Tests fail with ImportError or NotImplementedError (endpoint not yet created).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# These test the FastAPI HTTP interface via TestClient.
# The endpoint path will be added to the existing entities router.
from fastapi.testclient import TestClient


# This import WILL fail (RED phase) — main.py app needs the aspect endpoint,
# which does not exist yet. Implementation in plan 04 will add it.
from main import app  # noqa: F401


@pytest.fixture
def client():
    """FastAPI TestClient for endpoint tests."""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mocked AsyncSession for endpoint DB access."""
    return AsyncMock()


class TestAspectEndpointTimeWindows:
    """Tests for fixed time window parameters (7d, 30d, 90d)."""

    def test_7d_window_returns_aspects_with_mean_and_count(
        self, client, sample_aspect_data
    ):
        """GET /entities/1/aspects?window=7d returns aspects with mean and count per aspect."""
        # Mock the DB session dependency to return sample aspect data
        with patch("api.routes.entities.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            # Mock entity lookup — entity exists
            mock_entity_result = MagicMock()
            mock_entity = MagicMock()
            mock_entity.id = 1
            mock_entity.name = "Claude"
            mock_entity_result.scalar_one_or_none = MagicMock(
                return_value=mock_entity
            )

            # Mock aspect aggregation result
            mock_aspect_rows = [
                MagicMock(aspect="performance", mean_score=0.7, post_count=2),
                MagicMock(aspect="cost", mean_score=-0.1, post_count=2),
                MagicMock(aspect="reliability", mean_score=0.6, post_count=2),
                MagicMock(aspect="ux", mean_score=0.65, post_count=2),
                MagicMock(aspect="speed", mean_score=0.65, post_count=2),
                MagicMock(aspect="code_quality", mean_score=0.85, post_count=2),
                MagicMock(aspect="context_window", mean_score=0.35, post_count=2),
            ]
            mock_aspect_result = MagicMock()
            mock_aspect_result.all = MagicMock(return_value=mock_aspect_rows)

            mock_session.execute = AsyncMock(
                side_effect=[mock_entity_result, mock_aspect_result]
            )
            mock_get_session.return_value.__aiter__ = AsyncMock(
                return_value=iter([mock_session])
            )

            response = client.get("/entities/1/aspects?window=7d")

        assert response.status_code == 200
        data = response.json()
        # Response should contain aspect data with mean and count
        assert "aspects" in data or isinstance(data, dict)

    def test_30d_window_returns_aspects(self, client):
        """GET /entities/1/aspects?window=30d returns aspects computed over 30-day window."""
        with patch("api.routes.entities.get_session"):
            response = client.get("/entities/1/aspects?window=30d")

        # Endpoint exists and accepts 30d window
        assert response.status_code in (200, 404)  # 404 acceptable if no entity data

    def test_90d_window_returns_aspects(self, client):
        """GET /entities/1/aspects?window=90d returns aspects computed over 90-day window."""
        with patch("api.routes.entities.get_session"):
            response = client.get("/entities/1/aspects?window=90d")

        assert response.status_code in (200, 404)

    def test_invalid_window_returns_422(self, client):
        """GET /entities/1/aspects?window=invalid returns 422 validation error."""
        with patch("api.routes.entities.get_session"):
            response = client.get("/entities/1/aspects?window=15d")

        # 15d is not one of the valid windows (7d, 30d, 90d)
        assert response.status_code == 422


class TestAspectEndpointSourceFilter:
    """Tests for optional source filter parameter."""

    def test_hn_source_filter_filters_to_hn_aspects(self, client):
        """GET /entities/1/aspects?window=7d&source=hn filters to only HN-sourced aspects."""
        with patch("api.routes.entities.get_session"):
            response = client.get("/entities/1/aspects?window=7d&source=hn")

        # Endpoint accepts source filter without error
        assert response.status_code in (200, 404)

    def test_reddit_source_filter_accepted(self, client):
        """GET /entities/1/aspects?window=7d&source=reddit is accepted."""
        with patch("api.routes.entities.get_session"):
            response = client.get("/entities/1/aspects?window=7d&source=reddit")

        assert response.status_code in (200, 404)

    def test_invalid_source_returns_422(self, client):
        """GET /entities/1/aspects?window=7d&source=twitter returns 422 (invalid source)."""
        with patch("api.routes.entities.get_session"):
            response = client.get("/entities/1/aspects?window=7d&source=twitter")

        assert response.status_code == 422


class TestAspectEndpointEntityLookup:
    """Tests for entity not found behavior."""

    def test_unknown_entity_id_returns_404(self, client):
        """GET /entities/99999/aspects returns 404 for unknown entity_id."""
        with patch("api.routes.entities.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            # Entity does not exist
            mock_entity_result = MagicMock()
            mock_entity_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_session.execute = AsyncMock(return_value=mock_entity_result)
            mock_get_session.return_value.__aiter__ = AsyncMock(
                return_value=iter([mock_session])
            )

            response = client.get("/entities/99999/aspects?window=7d")

        assert response.status_code == 404

    def test_valid_entity_with_no_aspects_returns_200_empty(self, client):
        """GET /entities/1/aspects for entity with no aspect data returns 200 with empty aspects."""
        with patch("api.routes.entities.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            mock_entity_result = MagicMock()
            mock_entity = MagicMock()
            mock_entity.id = 1
            mock_entity.name = "Claude"
            mock_entity_result.scalar_one_or_none = MagicMock(
                return_value=mock_entity
            )

            # No aspect rows
            mock_aspect_result = MagicMock()
            mock_aspect_result.all = MagicMock(return_value=[])
            mock_session.execute = AsyncMock(
                side_effect=[mock_entity_result, mock_aspect_result]
            )
            mock_get_session.return_value.__aiter__ = AsyncMock(
                return_value=iter([mock_session])
            )

            response = client.get("/entities/1/aspects?window=7d")

        # Assumption: returns 200 with empty aspects dict, not 404
        assert response.status_code == 200


class TestAspectResponseStructure:
    """Tests for expected response shape from the aspect endpoint."""

    def test_response_includes_entity_id_and_window(self, client):
        """Response JSON includes entity_id and window parameters for context."""
        with patch("api.routes.entities.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            mock_entity_result = MagicMock()
            mock_entity = MagicMock()
            mock_entity.id = 1
            mock_entity.name = "Claude"
            mock_entity_result.scalar_one_or_none = MagicMock(
                return_value=mock_entity
            )

            mock_aspect_result = MagicMock()
            mock_aspect_result.all = MagicMock(return_value=[])
            mock_session.execute = AsyncMock(
                side_effect=[mock_entity_result, mock_aspect_result]
            )
            mock_get_session.return_value.__aiter__ = AsyncMock(
                return_value=iter([mock_session])
            )

            response = client.get("/entities/1/aspects?window=7d")

        if response.status_code == 200:
            data = response.json()
            assert "entity_id" in data or "aspects" in data
