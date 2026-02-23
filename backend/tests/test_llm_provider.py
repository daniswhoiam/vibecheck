"""Tests for LLM provider abstraction (Phase 8 — Tier 2 LLM aspect extraction).

Tests cover:
- Provider factory selection via LLM_PROVIDER env var (Groq, OpenAI, unknown)
- LLM_MODEL env var overrides default model_id on instantiated provider
- GroqProvider.extract_aspects() returns valid dict keyed by entity name
- GroqProvider.extract_aspects() raises after max retries on API failure
- Pydantic validation rejects scores outside [-1.0, 1.0] bounds
- Pydantic validation rejects unknown aspect names in LLM output

RED phase: All tests fail with ImportError (modules not yet created).
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# These imports WILL fail (RED phase) — modules do not exist yet.
# Implementation in plans 02-03 will create them.
from pipeline.services.llm_provider import (  # noqa: F401
    get_llm_provider,
    GroqProvider,
    OpenAIProvider,
    LLMResponseSchema,
)


class TestProviderFactory:
    """Tests for get_llm_provider() factory function."""

    def test_groq_env_returns_groq_provider(self, monkeypatch):
        """LLM_PROVIDER=groq → factory returns GroqProvider instance."""
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        with patch("pipeline.services.llm_provider.Groq"):
            provider = get_llm_provider()

        assert isinstance(provider, GroqProvider)

    def test_openai_env_returns_openai_provider(self, monkeypatch):
        """LLM_PROVIDER=openai → factory returns OpenAIProvider instance."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("pipeline.services.llm_provider.AsyncOpenAI"):
            provider = get_llm_provider()

        assert isinstance(provider, OpenAIProvider)

    def test_unknown_provider_raises_value_error(self, monkeypatch):
        """Unknown LLM_PROVIDER → factory raises ValueError."""
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider()

    def test_llm_model_env_overrides_default_on_groq(self, monkeypatch):
        """LLM_MODEL env var overrides the default model_id on GroqProvider."""
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("LLM_MODEL", "llama-3.1-8b-instant")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        with patch("pipeline.services.llm_provider.Groq"):
            provider = get_llm_provider()

        assert provider.model_id == "llama-3.1-8b-instant"

    def test_llm_model_env_overrides_default_on_openai(self, monkeypatch):
        """LLM_MODEL env var overrides the default model_id on OpenAIProvider."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("pipeline.services.llm_provider.AsyncOpenAI"):
            provider = get_llm_provider()

        assert provider.model_id == "gpt-4o"


class TestGroqProviderExtractAspects:
    """Tests for GroqProvider.extract_aspects() behavior."""

    @pytest.mark.asyncio
    async def test_extract_aspects_returns_entity_keyed_dict(self, monkeypatch):
        """GroqProvider.extract_aspects() with mocked client returns dict keyed by entity name."""
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        mock_response_json = (
            '{"entities": [{"name": "Claude", "aspects": {'
            '"performance": 0.8, "cost": -0.2, "reliability": 0.5, '
            '"ux": 0.6, "speed": 0.7, "code_quality": 0.9, "context_window": 0.3}}]}'
        )

        mock_choice = MagicMock()
        mock_choice.message.content = mock_response_json
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_groq_client = MagicMock()
        mock_groq_client.chat.completions.create = MagicMock(
            return_value=mock_completion
        )

        with patch("pipeline.services.llm_provider.Groq", return_value=mock_groq_client):
            provider = GroqProvider(api_key="test-key")

        result = await provider.extract_aspects(
            post_text="Claude is great for coding",
            entity_names=["Claude"],
        )

        assert isinstance(result, dict)
        assert "Claude" in result
        assert "performance" in result["Claude"]
        assert result["Claude"]["performance"] == 0.8

    @pytest.mark.asyncio
    async def test_extract_aspects_raises_after_retries_on_api_failure(
        self, monkeypatch
    ):
        """GroqProvider.extract_aspects() raises exception after 3 retries when API fails."""
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        mock_groq_client = MagicMock()
        mock_groq_client.chat.completions.create = MagicMock(
            side_effect=Exception("Groq API rate limit exceeded")
        )

        with patch("pipeline.services.llm_provider.Groq", return_value=mock_groq_client):
            provider = GroqProvider(api_key="test-key")

        # Should raise after exhausting all retries (tenacity)
        with pytest.raises(Exception):
            await provider.extract_aspects(
                post_text="Test post",
                entity_names=["Claude"],
            )

        # API was called at least once (retried)
        assert mock_groq_client.chat.completions.create.call_count >= 1


class TestLLMResponseSchemaValidation:
    """Tests for LLMResponseSchema Pydantic validation."""

    def test_score_above_1_fails_validation(self):
        """LLM output with score > 1.0 fails Pydantic validation (AspectScoresSchema bounds)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LLMResponseSchema(
                entities=[
                    {
                        "name": "Claude",
                        "aspects": {
                            "performance": 1.5,  # Out of bounds: > 1.0
                            "cost": 0.0,
                            "reliability": 0.0,
                            "ux": 0.0,
                            "speed": 0.0,
                            "code_quality": 0.0,
                            "context_window": 0.0,
                        },
                    }
                ]
            )

    def test_score_below_minus_1_fails_validation(self):
        """LLM output with score < -1.0 fails Pydantic validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LLMResponseSchema(
                entities=[
                    {
                        "name": "Claude",
                        "aspects": {
                            "performance": -1.5,  # Out of bounds: < -1.0
                            "cost": 0.0,
                            "reliability": 0.0,
                            "ux": 0.0,
                            "speed": 0.0,
                            "code_quality": 0.0,
                            "context_window": 0.0,
                        },
                    }
                ]
            )

    def test_unknown_aspect_name_fails_validation(self):
        """LLM output with unknown aspect name fails Pydantic validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LLMResponseSchema(
                entities=[
                    {
                        "name": "Claude",
                        "aspects": {
                            "nonexistent_aspect": 0.5,  # Unknown aspect
                            "performance": 0.0,
                            # Missing required fields also raises ValidationError
                        },
                    }
                ]
            )

    def test_valid_response_passes_validation(self):
        """LLM output with valid scores and aspect names passes validation."""
        response = LLMResponseSchema(
            entities=[
                {
                    "name": "Claude",
                    "aspects": {
                        "performance": 0.8,
                        "cost": -0.2,
                        "reliability": 0.5,
                        "ux": 0.6,
                        "speed": 0.7,
                        "code_quality": 0.9,
                        "context_window": 0.3,
                    },
                }
            ]
        )
        assert len(response.entities) == 1
        assert response.entities[0].name == "Claude"
        assert response.entities[0].aspects.performance == 0.8
