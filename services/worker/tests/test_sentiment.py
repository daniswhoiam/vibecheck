"""Unit tests for the sentiment model interface.

Uses the real model (downloaded to the HF cache on first run): the contract
under test is "known text in -> sensible score/label out", which a mock cannot
verify. The analyzer is session-scoped so the model loads once.
"""

import math

import pytest
from worker.sentiment import SentimentAnalyzer


@pytest.fixture(scope="session")
def analyzer() -> SentimentAnalyzer:
    return SentimentAnalyzer()


def test_positive_text_yields_positive_label_and_high_score(analyzer: SentimentAnalyzer) -> None:
    result = analyzer.analyze("I absolutely love this tool, it works great!")
    assert result.label == "positive"
    assert 0.5 < result.score <= 1.0


def test_negative_text_yields_negative_label_and_low_score(analyzer: SentimentAnalyzer) -> None:
    result = analyzer.analyze("This is terrible, it crashes constantly and lost my work.")
    assert result.label == "negative"
    assert 0.0 <= result.score < 0.5


def test_raw_output_holds_full_probability_distribution(analyzer: SentimentAnalyzer) -> None:
    result = analyzer.analyze("The weather is okay.")
    assert set(result.raw) == {"negative", "neutral", "positive"}
    assert math.isclose(sum(result.raw.values()), 1.0, abs_tol=1e-3)


def test_analyzer_exposes_model_identity(analyzer: SentimentAnalyzer) -> None:
    assert analyzer.model_name == "cardiffnlp/twitter-roberta-base-sentiment-latest"
    assert analyzer.model_version is None or isinstance(analyzer.model_version, str)
