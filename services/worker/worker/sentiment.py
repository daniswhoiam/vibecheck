"""Sentiment model interface.

The rest of the worker only sees ``analyze(text) -> SentimentResult``, so the
model can be swapped by replacing this one class. Scores live on a [0, 1]
scale (0 = maximally negative, 0.5 = neutral, 1 = maximally positive) to match
the semantics already used by the dashboard and seed data.
"""

from dataclasses import dataclass
from typing import Any, cast

from transformers import pipeline

MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"


@dataclass(frozen=True, slots=True)
class SentimentResult:
    score: float
    label: str
    raw: dict[str, float]


class SentimentAnalyzer:
    """Loads the model eagerly; construct once at worker startup."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self._pipeline = pipeline("text-classification", model=model_name, top_k=None)
        self.model_name = model_name
        # The resolved HF commit hash of the downloaded snapshot. Recorded as
        # model_version so a model update produces NEW analysis rows instead of
        # silently colliding with old verdicts on the DB's natural key.
        self.model_version: str | None = getattr(self._pipeline.model.config, "_commit_hash", None)

    def analyze(self, text: str) -> SentimentResult:
        # truncation: real posts can exceed the model's 512-token window.
        # cast: the pipeline's __call__ is typed too loosely for strict mypy.
        scores = cast("list[dict[str, Any]]", self._pipeline(text, truncation=True)[0])
        raw = {str(s["label"]): float(s["score"]) for s in scores}
        score = 0.5 + (raw["positive"] - raw["negative"]) / 2
        label = max(raw, key=lambda k: raw[k])
        return SentimentResult(score=score, label=label, raw=raw)
