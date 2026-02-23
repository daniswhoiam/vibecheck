"""Sentiment classification service for VibeCheck Phase 7.

Provides zero-shot sentiment classification using a cross-encoder NLI model.
Model is loaded on-demand per job run and unloaded after classification to minimize
memory footprint between 6-hour collection cycles.

Classification labels: Positive / Negative / Neutral
Confidence score: float 0.0–1.0 (higher = more confident in the top label)

NOTE: Originally used knowledgator/gliclass-base-v1.0-lw (GLiClass architecture),
but that model type is not compatible with transformers>=5.0. Switched to
cross-encoder/nli-MiniLM2-L6-H768 which is a compact (~100MB) NLI model that
supports zero-shot-classification in standard transformers.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Model identifier — compact NLI model compatible with transformers >= 4.39.
# cross-encoder/nli-MiniLM2-L6-H768: ~100MB, fast on CPU, good zero-shot perf.
DEFAULT_MODEL_ID = "cross-encoder/nli-MiniLM2-L6-H768"

# Candidate labels for zero-shot classification (order matters — first is ranked highest
# by the NLI model when probability mass is split evenly, so put most common first)
SENTIMENT_LABELS = ["Positive", "Negative", "Neutral"]

# Truncate post text to ~512 tokens. 2000 chars ≈ 500 tokens for typical English text.
MAX_CHARS = 2000

# Initial batch size — conservative start, safe for 1.5GB memory budget.
# Increase to 16 after benchmarking first production run if memory stays < 1.0 GB.
DEFAULT_BATCH_SIZE = 8


class SentimentClassifier:
    """Zero-shot sentiment classifier using GliClass.

    On-demand loading strategy: model is loaded once per classify() call
    (i.e., once per job run), then explicitly unloaded to free memory.
    This trades ~3s load time for minimal baseline memory between job cycles.

    Usage:
        classifier = SentimentClassifier()
        results = await classifier.classify(["Great tool!", "Terrible latency"])
        # [{"label": "Positive", "score": 0.92}, {"label": "Negative", "score": 0.88}]
    """

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, batch_size: int = DEFAULT_BATCH_SIZE):
        self.model_id = model_id
        self.batch_size = batch_size
        self._pipeline: Optional[object] = None

    def _load_pipeline(self):
        """Load the zero-shot classification pipeline synchronously.

        Called inside asyncio.to_thread() to avoid blocking the event loop.
        Uses device=-1 (CPU) explicitly — GPU not guaranteed in deployment.
        """
        from transformers import pipeline as hf_pipeline
        logger.info("Loading GliClass model: %s", self.model_id)
        self._pipeline = hf_pipeline(
            "zero-shot-classification",
            model=self.model_id,
            device=-1,  # CPU — GPU not available in Render Standard tier
        )
        logger.info("GliClass model loaded successfully")

    def _unload_pipeline(self):
        """Unload the model to free memory after job completes."""
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
            # Hint to Python GC — does not guarantee immediate deallocation
            # but reduces peak memory duration significantly
            import gc
            gc.collect()
            logger.info("GliClass model unloaded")

    def _classify_batch_sync(self, texts: list[str]) -> list[dict]:
        """Run zero-shot classification on a batch synchronously.

        Called inside asyncio.to_thread(). Processes texts one-by-one rather
        than as a true batch to prevent memory spikes from variable-length inputs.
        The 'batch' here refers to the query batch size from the calling job —
        we load the model once for the whole batch.
        """
        results = []
        for text in texts:
            truncated = text[:MAX_CHARS]
            result = self._pipeline(
                truncated,
                SENTIMENT_LABELS,
                multi_label=False,  # Single dominant label
            )
            # result structure: {"labels": [...ranked], "scores": [...ranked], "sequence": ...}
            results.append({
                "label": result["labels"][0],   # Top-ranked label
                "score": float(result["scores"][0]),  # Confidence for top label
            })
        return results

    async def classify(self, texts: list[str]) -> list[dict]:
        """Classify a list of texts for sentiment.

        Loads the model if not already loaded, processes all texts, then
        unloads the model. The full load-classify-unload lifecycle happens
        within a single classify() call.

        All I/O-bound work runs in asyncio.to_thread() so the event loop
        is not blocked during model load or inference.

        Args:
            texts: List of text strings to classify. Each will be truncated
                   to MAX_CHARS before classification.

        Returns:
            List of dicts with "label" (str) and "score" (float 0-1).
            Same order as input texts.

        Example:
            [{"label": "Positive", "score": 0.92}, {"label": "Negative", "score": 0.85}]
        """
        if not texts:
            return []

        try:
            # Load model in thread pool (blocks ~2-5s, avoids event loop freeze)
            await asyncio.to_thread(self._load_pipeline)

            # Classify all texts in thread pool (inference can be CPU-intensive)
            results = await asyncio.to_thread(self._classify_batch_sync, texts)

            logger.info(
                "Classified %d texts with GliClass (label distribution: %s)",
                len(results),
                {label: sum(1 for r in results if r["label"] == label) for label in SENTIMENT_LABELS},
            )
            return results

        finally:
            # Always unload, even if classification fails partway through
            self._unload_pipeline()
