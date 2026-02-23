"""LLM provider abstraction for Tier 2 aspect-level sentiment extraction.

Provides a strategy-pattern interface for swapping LLM backends via env vars.
Default provider: Groq (Llama 3.3 70B). Alternate: OpenAI (GPT-4o-mini).

Usage:
    provider = get_llm_provider()  # reads LLM_PROVIDER env var
    result = await provider.extract_aspects(post_text, entity_names)
    # result: {"Claude": {"performance": 0.8, "cost": -0.2, ...}, ...}
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level imports for patchability in tests.
# Both SDKs are lazy at the class level (not forced at import time), but the
# *names* must live in this module's namespace so tests can patch them.
# ---------------------------------------------------------------------------
try:
    from groq import Groq  # noqa: F401
except ImportError:  # pragma: no cover
    Groq = None  # type: ignore[assignment,misc]

try:
    from openai import AsyncOpenAI  # noqa: F401
except ImportError:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Retry imports
# ---------------------------------------------------------------------------
from tenacity import retry, stop_after_attempt, wait_exponential  # noqa: E402

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a sentiment analysis expert. Extract aspect-level sentiment scores "
    "for each AI tool or model mentioned in the post.\n\n"
    "Fixed aspects: performance, cost, reliability, ux, speed, code_quality, context_window\n"
    "Score range: -1.0 (very negative) to 1.0 (very positive). Use 0.0 for neutral/not mentioned.\n"
    "Output ONLY valid JSON, no markdown, no explanations."
)

# ---------------------------------------------------------------------------
# Pydantic schemas — validate LLM output and enforce score bounds
# ---------------------------------------------------------------------------


class AspectScoresSchema(BaseModel):
    """Validated aspect scores for one entity.

    All seven aspects are required. Unknown aspects are silently ignored
    (extra='ignore'). Scores must be in [-1.0, 1.0].
    """

    model_config = ConfigDict(extra="ignore")

    performance: float = Field(ge=-1.0, le=1.0)
    cost: float = Field(ge=-1.0, le=1.0)
    reliability: float = Field(ge=-1.0, le=1.0)
    ux: float = Field(ge=-1.0, le=1.0)
    speed: float = Field(ge=-1.0, le=1.0)
    code_quality: float = Field(ge=-1.0, le=1.0)
    context_window: float = Field(ge=-1.0, le=1.0)


class EntityAspectsSchema(BaseModel):
    """One entity with its aspect scores."""

    name: str
    aspects: AspectScoresSchema


class LLMResponseSchema(BaseModel):
    """Validated top-level LLM response containing per-entity aspect scores."""

    entities: list[EntityAspectsSchema]


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Abstract interface for LLM providers (Groq, OpenAI, etc.)."""

    @abstractmethod
    async def extract_aspects(
        self,
        post_text: str,
        entity_names: list[str],
    ) -> dict[str, dict[str, float]]:
        """Extract aspect-level sentiment per entity.

        Returns:
            {
                "Claude": {"performance": 0.8, "cost": -0.2, ...},
                "Cursor": {"performance": 0.5, "speed": 0.7, ...},
                ...
            }
        """


# ---------------------------------------------------------------------------
# GroqProvider
# ---------------------------------------------------------------------------


class GroqProvider(LLMProvider):
    """Groq LLM provider using Llama 3.3 70B with JSON mode.

    Uses asyncio.to_thread() because the Groq SDK is synchronous — never
    blocks the async event loop directly.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "llama-3.3-70b-versatile",
    ) -> None:
        self.model_id = model_id
        self.client = Groq(api_key=api_key or os.getenv("GROQ_API_KEY"))  # type: ignore[misc]

    async def extract_aspects(
        self,
        post_text: str,
        entity_names: list[str],
    ) -> dict[str, dict[str, float]]:
        from utils.constants import VALID_ASPECTS

        entity_list = ", ".join(entity_names) if entity_names else "unknown entity"
        aspect_list = ", ".join(sorted(VALID_ASPECTS))
        truncated_text = post_text[:3000]

        user_prompt = (
            f"Post text:\n{truncated_text}\n\n"
            f"Entities mentioned: {entity_list}\n\n"
            f"Return JSON with these aspects per entity: {aspect_list}\n"
            '{"entities": [{"name": "entity_name", "aspects": {"performance": 0.0, ...}}]}'
        )

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        )
        def _call_sync() -> str:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1000,
            )
            return response.choices[0].message.content

        json_str = await asyncio.to_thread(_call_sync)
        raw = json.loads(json_str)

        try:
            validated = LLMResponseSchema(**raw)
        except Exception as exc:
            logger.warning(
                "GroqProvider: LLM output failed Pydantic validation: %s | raw=%s",
                exc,
                json_str[:200],
            )
            raise

        return {e.name: dict(e.aspects) for e in validated.entities}


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4o-mini provider for aspect extraction.

    Uses AsyncOpenAI which is natively async — no asyncio.to_thread needed.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "gpt-4o-mini",
    ) -> None:
        self.model_id = model_id
        self.client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))  # type: ignore[misc]

    async def extract_aspects(
        self,
        post_text: str,
        entity_names: list[str],
    ) -> dict[str, dict[str, float]]:
        from utils.constants import VALID_ASPECTS

        entity_list = ", ".join(entity_names) if entity_names else "unknown entity"
        aspect_list = ", ".join(sorted(VALID_ASPECTS))
        truncated_text = post_text[:3000]

        user_prompt = (
            f"Post text:\n{truncated_text}\n\n"
            f"Entities mentioned: {entity_list}\n\n"
            f"Return JSON with these aspects per entity: {aspect_list}\n"
            '{"entities": [{"name": "entity_name", "aspects": {"performance": 0.0, ...}}]}'
        )

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        )
        async def _call_async() -> str:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1000,
            )
            return response.choices[0].message.content

        json_str = await _call_async()
        raw = json.loads(json_str)

        try:
            validated = LLMResponseSchema(**raw)
        except Exception as exc:
            logger.warning(
                "OpenAIProvider: LLM output failed Pydantic validation: %s | raw=%s",
                exc,
                json_str[:200],
            )
            raise

        return {e.name: dict(e.aspects) for e in validated.entities}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_llm_provider() -> LLMProvider:
    """Instantiate the LLM provider configured via environment variables.

    Env vars:
        LLM_PROVIDER: "groq" (default) or "openai"
        LLM_MODEL:    model ID override (optional; uses provider default if unset)

    Returns:
        LLMProvider instance (GroqProvider or OpenAIProvider)

    Raises:
        ValueError: if LLM_PROVIDER is not a known value
    """
    provider_name = os.getenv("LLM_PROVIDER", "groq").lower()
    model_id = os.getenv("LLM_MODEL", None)

    if provider_name == "groq":
        kwargs = {"model_id": model_id} if model_id else {}
        return GroqProvider(**kwargs)
    elif provider_name == "openai":
        kwargs = {"model_id": model_id} if model_id else {}
        return OpenAIProvider(**kwargs)
    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider_name}'. Supported: groq, openai"
        )
