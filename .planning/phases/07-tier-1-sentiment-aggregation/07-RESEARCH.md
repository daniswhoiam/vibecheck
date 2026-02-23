# Phase 7: Tier 1 Sentiment + Aggregation - Research

**Researched:** 2026-02-23
**Domain:** Zero-shot text classification, sentiment scoring, time-series aggregation, batch processing
**Confidence:** HIGH

## Summary

Phase 7 implements a two-stage sentiment pipeline: (1) zero-shot classification using GliClass to score unscored posts, and (2) incremental aggregation of sentiment into per-source time-series rollups. The user chose GliClass (zero-shot) over fine-tuned RoBERTa, which eliminates training overhead and simplifies deployment. The pipeline chains after each collection job completes, keeping data consistent. Key research focus: batch processing patterns for memory efficiency (Render's 1.5GB limit), JSONB aggregation patterns in PostgreSQL for source breakdowns, and managing model residency vs on-demand loading.

**Primary recommendation:** Use Hugging Face zero-shot-classification pipeline with GliClass (knowledgator/gliclass-base-v1.0-lw or -modern-base-v2.0) for 3-class sentiment (Positive/Negative/Neutral), process unscored posts in batches with memory-aware batch sizing, store label+confidence on Post model, compute daily rollups incrementally with source_breakdown as JSONB, and use on-demand model loading with cleanup after job completion.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Scoring strategy:**
- Use GliClass (zero-shot classification) instead of RoBERTa
- 3-class labels: Positive / Negative / Neutral
- Score using post body text (title + body), truncated if needed for model token limits
- Only process new/unscored posts (where sentiment columns are NULL) — not full rescore
- Incremental: each run processes only posts that haven't been scored yet

**Aggregation rollups:**
- Replace the v1.0 SentimentTimeseries concept entirely — new table, clean break
- Incremental aggregation: only recompute the current day's bucket each run
- Stats per rollup row: mean sentiment + post count, broken down per source
- Source breakdown stored as JSONB (e.g. `{hn: {mean: 0.4, count: 12}, reddit: {mean: -0.1, count: 8}}`)

**API changes:**
- Rewrite existing `/entities/{id}/sentiment` endpoint to query new rollup table — same URL, new response shape
- Source breakdown nested inside each timeseries data point (one call gets everything)
- Clean up ALL v1.0 remnants in Phase 7: remove dead Article/SentimentTimeseries imports from db/__init__.py, fix entity routes that reference old models, update schemas

**Pipeline chaining:**
- Chain: collect → score → aggregate as one pipeline per source
- Sentiment scoring runs after each collection job completes, not on a separate schedule
- Aggregation runs after scoring completes — data always consistent

### Claude's Discretion

- Sentiment storage format on Post model (label + confidence vs numeric score — pick what best supports aggregation and Tier 2 routing)
- Time granularity for rollups (daily only vs hourly+daily — pick based on 6-hour collection cycles)
- GliClass model loading strategy (on-demand vs resident — pick based on model size and typical deployment memory constraints, not Render-specific)
- Batch size for sentiment processing (pick based on model memory profile)
- Whether entity list endpoint includes latest sentiment score

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SENT-01 | Tier 1 RoBERTa classifier scores every post as positive/negative/neutral with confidence | GliClass zero-shot pipeline provides 3-class classification with confidence scores; user chose GliClass over RoBERTa. Storage: (1) Add sentiment_label (VARCHAR) + sentiment_score (FLOAT) to Post model, or (2) store numeric -1.0 to 1.0 score with class derivable from threshold. Incremental processing with NULL checks ensures only unscored posts are processed. |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| transformers | 4.39.0+ | Hugging Face pipeline interface for zero-shot classification | Industry standard for transformer-based NLP; zero-shot-classification pipeline frames classification as NLI (natural language inference) without needing training data |
| torch | 2.0.0+ | PyTorch backend for transformer models (required by transformers) | Standard deep learning framework for HuggingFace models; enables GPU/CPU flexibility and memory optimization |
| sqlalchemy | 2.0.35 (existing) | Async ORM for database operations | Already in stack; enables batch queries and incremental aggregation patterns |
| alembic | 1.14.0 (existing) | Schema migrations for new sentiment columns and rollup tables | Already in use; handles table creation for new aggregation structure |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncpg | 0.30.0 (existing) | Async PostgreSQL driver | Already in use; supports JSONB aggregation operations and batch inserts for rollups |
| psycopg | 3.1+ | Alternative: synchronous driver if async sentiment job proves complex | Only if async model inference creates coordination bottlenecks |

### Model / Implementation Choices

| Decision | Rationale |
|----------|-----------|
| **GliClass variant** | Choose `knowledgator/gliclass-base-v1.0-lw` (lightweight, ~0.2B params) for memory-constrained Render deployment. Fallback to `knowledgator/gliclass-modern-base-v2.0` if accuracy insufficient. Avoid large variants (0.4B+) given 1.5GB memory target and other process overhead. |
| **Sentiment storage** | Recommend `sentiment_label (VARCHAR: 'Positive'/'Negative'/'Neutral') + sentiment_score (FLOAT: 0-1)` on Post model. Allows both class-based logic and confidence-aware downstream filtering (Tier 2). Alternative: single `sentiment_score (-1.0 to 1.0)` with class derivable from threshold, simpler but loses confidence granularity. |
| **Rollup granularity** | Daily only (not hourly) matches 6-hour collection cycle; hourly would create many sparse buckets. Incremental: only recompute current UTC day's aggregate on each run, leaving past buckets immutable. |
| **Model loading** | On-demand (load once per job, unload after aggregation completes) vs resident (keep in memory across requests). Recommend on-demand for Render: minimizes baseline memory footprint, job runs ~30-60 min every 6 hours, model load/inference time (~2-3s) acceptable trade-off for <1.5GB guarantee. |
| **Batch size** | Start with batch_size=16-32 for zero-shot classification (depends on post body length). Benchmark: typical post ~500-1000 tokens; batch_size=16 at 512 max tokens ≈ 100-150 MB GPU + 50MB CPU overhead. Monitor Render memory dashboard; scale down if approaching 1.2GB. |

### Installation

```bash
pip install transformers==4.39.3 torch==2.0.1 --upgrade
# Also add to requirements.txt
```

## Architecture Patterns

### Recommended Project Structure

New sentiment pipeline integrates into `pipeline/` alongside data collection:

```
backend/
├── pipeline/
│   ├── jobs/
│   │   ├── collect_*.py              # Phase 6 (existing)
│   │   ├── score_sentiment.py         # NEW: sentiment scoring job
│   │   └── aggregate_sentiment.py     # NEW: sentiment rollup job
│   ├── services/
│   │   ├── sentiment_service.py       # NEW: SentimentClassifier, aggregation logic
│   │   ├── *_service.py               # Existing (filter, storage, etc.)
│   ├── scheduler.py                   # MODIFIED: add score + aggregate jobs
│   └── models.py                      # Pipeline model types (if needed)
├── db/
│   ├── models.py                      # MODIFIED: add sentiment_label, sentiment_score to Post
│   └── migrations/                    # NEW: 007_add_sentiment_columns.py, 008_create_sentiment_rollup_table.py
├── api/
│   ├── routes/
│   │   ├── entities.py                # MODIFIED: clean v1.0 SentimentTimeseries refs
│   │   └── sentiment.py               # MODIFIED: new rollup query logic
│   └── schemas/
│       └── sentiment.py               # MODIFIED: new response shape (source_breakdown)
└── ...
```

### Pattern 1: Zero-Shot Classification Pipeline

**What:** Load model once per job, classify batch of texts, unload to free memory.

**When to use:** Every sentiment scoring job run (after each collection job).

**Example:**

```python
# Source: Hugging Face transformers documentation
# https://huggingface.co/tasks/zero-shot-classification
from transformers import pipeline

class SentimentClassifier:
    """Lazy-load GliClass model for zero-shot classification."""

    def __init__(self, model_id: str = "knowledgator/gliclass-base-v1.0-lw"):
        self.model_id = model_id
        self.pipeline = None

    async def classify(self, texts: list[str]) -> list[dict]:
        """Classify texts in batch. Load model on first call, unload after."""
        try:
            # Lazy load on first call
            if self.pipeline is None:
                self.pipeline = pipeline(
                    "zero-shot-classification",
                    model=self.model_id,
                    device=0  # GPU if available, else CPU
                )

            candidate_labels = ["positive", "negative", "neutral"]
            results = []

            for text in texts:
                # Truncate to model max length (~512 tokens)
                truncated = text[:2000]  # ~500 tokens

                result = self.pipeline(
                    truncated,
                    candidate_labels,
                    multi_class=False  # Single label, not multi-label
                )

                # result format: {'labels': [...], 'scores': [...], 'sequence': ...}
                results.append({
                    'label': result['labels'][0],  # Top-ranked label
                    'score': result['scores'][0]   # Confidence 0-1
                })

            return results
        finally:
            # Cleanup: unload model to free memory
            if self.pipeline is not None:
                del self.pipeline
                self.pipeline = None
```

### Pattern 2: Incremental Aggregation with JSONB Source Breakdown

**What:** Query unprocessed posts for today, compute per-source stats, upsert into rollup table with JSONB breakdown.

**When to use:** After sentiment scoring completes.

**Example:**

```python
# SQLAlchemy + PostgreSQL JSONB aggregation
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert

async def aggregate_daily_sentiment(session: AsyncSession, entity_id: int):
    """Compute sentiment rollup for today, with source breakdown as JSONB."""

    from db.models import Post, PostEntityMention

    today_utc = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today_utc, datetime.min.time(), tzinfo=timezone.utc)
    today_end = datetime.combine(today_utc, datetime.max.time(), tzinfo=timezone.utc)

    # Query: for this entity on this day, group by source, compute mean + count
    # Using jsonb_object_agg to build {source: {mean: x, count: y}, ...}
    query = text("""
        SELECT
            entity_id,
            DATE(published_at) as rollup_date,
            jsonb_object_agg(
                source,
                jsonb_build_object(
                    'mean', ROUND(AVG(sentiment_score)::numeric, 3),
                    'count', COUNT(*)
                )
            ) as source_breakdown
        FROM posts p
        JOIN post_entity_mentions pem ON p.id = pem.post_id
        WHERE pem.entity_id = :entity_id
          AND p.published_at >= :day_start
          AND p.published_at < :day_end
          AND p.sentiment_score IS NOT NULL
        GROUP BY entity_id, DATE(published_at)
    """)

    result = await session.execute(query, {
        'entity_id': entity_id,
        'day_start': today_start,
        'day_end': today_end
    })

    row = result.first()
    if row:
        entity_id, rollup_date, source_breakdown = row

        # Upsert into sentiment_rollups table
        stmt = insert(SentimentRollup).values(
            entity_id=entity_id,
            rollup_date=rollup_date,
            sentiment_mean=func.jsonb_path_query_first(
                source_breakdown, '$.* | select(.mean)'
            ),  # Simplified; full logic computes weighted mean
            post_count=func.jsonb_path_query_first(
                source_breakdown, '$.* | select(.count)'
            ),
            source_breakdown=source_breakdown
        ).on_conflict_do_update(
            index_elements=['entity_id', 'rollup_date'],
            set_={
                'sentiment_mean': func.jsonb_path_query_first(
                    source_breakdown, '$.* | select(.mean)'
                ),
                'post_count': func.jsonb_path_query_first(
                    source_breakdown, '$.* | select(.count)'
                ),
                'source_breakdown': source_breakdown,
                'updated_at': func.now()
            }
        )

        await session.execute(stmt)
        await session.commit()
```

### Pattern 3: Pipeline Chaining in Scheduler

**What:** After collection job completes, trigger sentiment scoring, then aggregation, all in one wrapper.

**When to use:** Modify scheduler.py setup_jobs() to add sentiment + aggregation steps.

**Example:**

```python
# Modified scheduler job wrapper
async def run_collection_and_sentiment_pipeline(source: str, session: AsyncSession):
    """Chain: collect → score → aggregate for one source."""

    # Step 1: Collect (existing job)
    collect_fn = {
        'hackernews': run_collect_hackernews,
        'reddit': run_collect_reddit,
        # ...
    }[source]

    collect_stats = await collect_fn(session)
    logger.info(f"{source} collected {collect_stats['posts_added']} posts")

    # Step 2: Score unscored posts from this source
    sentiment_stats = await score_sentiment_job(
        session, source_filter=source
    )
    logger.info(f"{source} scored {sentiment_stats['posts_scored']} posts")

    # Step 3: Aggregate for all entities mentioned in new/scored posts
    agg_stats = await aggregate_sentiment_job(session)
    logger.info(f"Aggregation updated {agg_stats['rollups_updated']} entity-days")

    return {
        'collection': collect_stats,
        'sentiment': sentiment_stats,
        'aggregation': agg_stats
    }
```

### Anti-Patterns to Avoid

- **Loading model per-request:** Avoid loading GliClass in the API endpoint. Load once per job, not per classification. API should only query pre-computed sentiment from database.
- **Rescoring all posts:** Don't rerun sentiment on already-scored posts. Always filter `WHERE sentiment_score IS NULL` to process only new/unscored posts.
- **Synchronous model inference in async job:** Use thread pools (executor) if transformers inference becomes a bottleneck, or pre-compute sentiment in a subprocess. Don't block the async event loop on GPU operations.
- **Storing raw scores without label:** Storing only numeric score (-1 to 1) loses confidence information needed for Tier 2 LLM routing. Always store label + confidence pair.
- **Hardcoding Render-specific memory limits:** Don't optimize for Render memory only; design for generic 1.5GB constraint. This allows future multi-cloud deployment.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Zero-shot classification | Custom transformer wrapper, custom label ranking | Hugging Face `pipeline("zero-shot-classification")` | Handles tokenization, label encoding, cross-entropy scoring, ranking. Community-maintained; avoids subtle bugs in NLI task setup. |
| Batch sentiment processing | Manual tokenization + forward pass loop | transformers pipeline with batch support or transformers.utils.batch_feature(). Or use sentence-transformers for structured batching. | Auto-handles variable sequence lengths, padding, attention masks. Pre-optimized for GPU memory. |
| PostgreSQL aggregation | Application-side grouping and averaging | PostgreSQL `jsonb_object_agg()`, `AVG()`, `COUNT()` with GROUP BY | Database-level aggregation is 10-100x faster, especially with indexes. JSONB functions are optimized; custom JSON serialization in app is slower and more error-prone. |
| Model memory management | Manual del/garbage collection | transformers.utils.move_model_to_device(), del + torch.cuda.empty_cache() | These handle device-specific cleanup correctly. Manual approach misses edge cases (dtype conflicts, memory fragmentation). |

**Key insight:** Zero-shot classification and JSONB aggregation are "simple in principle, complex in practice" — the libraries handle dozens of edge cases (sequence length edge cases, numeric precision in aggregates, memory fragmentation) that custom code would need to debug.

## Common Pitfalls

### Pitfall 1: Model Loading Blocks the Async Event Loop

**What goes wrong:** Loading a transformer model (2-5 seconds) in an async job blocks all other requests until load completes.

**Why it happens:** HuggingFace transformers load models synchronously. If you call `pipeline()` in an async function, the entire async context freezes until the model is loaded.

**How to avoid:**
- Load model once at job startup, not per request.
- Or use `asyncio.to_thread()` to offload model loading to a thread pool:
  ```python
  import asyncio
  pipeline = await asyncio.to_thread(
      lambda: pipeline("zero-shot-classification", model="...")
  )
  ```

**Warning signs:** Long latency spikes in other API endpoints during sentiment job runs; scheduler logs show sentiment job starting but classification taking 10+ seconds for small batches.

### Pitfall 2: Sentiment Scoring OOM (Out Of Memory)

**What goes wrong:** Processing a batch of 100+ posts with large bodies (2000+ token posts) causes GPU/CPU memory to spike above 1.5GB, triggering Render restart.

**Why it happens:** Transformers models allocate memory proportional to input length squared (attention mechanism). batch_size=32 at 512 tokens vs batch_size=32 at 2000 tokens is 16x difference in memory.

**How to avoid:**
- Truncate post bodies to 2000 chars (~512 tokens) before classification.
- Start batch_size=16, benchmark memory on typical posts, scale up only if <1.0GB.
- Monitor Render memory metrics during first production run (check dashboard under "Metrics").

**Warning signs:** Process memory jumps to 1.4GB+ in Render logs; sentiment job exits with "Killed" (OOM) after processing ~50 posts.

### Pitfall 3: Full Rescore Instead of Incremental

**What goes wrong:** Running sentiment classifier on ALL posts, not just unscored ones. With millions of posts, this takes hours and wastes resources.

**Why it happens:** Forgetting `WHERE sentiment_score IS NULL` filter in the post query.

**How to avoid:**
- Always query `SELECT ... FROM posts WHERE sentiment_score IS NULL`.
- Add a unit test that verifies already-scored posts are skipped.
- Log the count of posts being scored; if count suddenly jumps to millions, something is wrong.

**Warning signs:** Sentiment job suddenly takes 3+ hours (normally ~30 min); logs show "scored 1M posts" on a run (impossible if only new posts are scored).

### Pitfall 4: JSONB Aggregation Includes Null Scores

**What goes wrong:** Source breakdown includes posts with `sentiment_score IS NULL`, producing invalid aggregates (mean is NULL or incorrect).

**Why it happens:** Forgetting `WHERE p.sentiment_score IS NOT NULL` in the aggregation query.

**How to avoid:**
- Test aggregation query manually in psql before merging.
- Add constraint check: source_breakdown should have 4 sources (HN, Reddit, Discourse, Dev.to); if only 1-2 sources appear, inspect the query.

**Warning signs:** Frontend shows "No data" for sentiment on days when posts were collected; API returns empty source_breakdown `{}` or single-source breakdowns.

### Pitfall 5: Confidence Threshold Confusion

**What goes wrong:** Storing confidence score (0-1) but treating it as sentiment label (-1 to 1), or vice versa. Downstream Tier 2 logic expects one format but gets the other.

**Why it happens:** Zero-shot pipeline outputs confidence as 0-1 (higher = more confident), not -1 to 1 sentiment scale. Easy to mix up.

**How to avoid:**
- Explicitly document storage: `sentiment_label: {'Positive', 'Negative', 'Neutral'}` and `sentiment_score: float in [0, 1]`.
- Map label to numeric score for API: `Positive -> +1.0, Neutral -> 0.0, Negative -> -1.0` in serialization (not storage).
- Tier 2 uses label directly, not score: `if label == 'Positive': check_performance_mentions()`.

**Warning signs:** Tier 2 LLM routing logic gets wrong label; frontend shows inverted sentiment (negative when should be positive).

## Code Examples

Verified patterns from official sources:

### Zero-Shot Classification with Truncation

```python
# Source: https://huggingface.co/tasks/zero-shot-classification
from transformers import pipeline

# Load once per job
classifier = pipeline(
    "zero-shot-classification",
    model="knowledgator/gliclass-base-v1.0-lw",
    device=0  # GPU 0, or -1 for CPU
)

# Classify with truncation
text = post.title + " " + post.body  # Combine title + body
text_truncated = text[:2000]  # Truncate to ~512 tokens

result = classifier(
    text_truncated,
    candidate_labels=["positive", "negative", "neutral"],
    multi_class=False
)

label = result['labels'][0]           # e.g., 'positive'
confidence = result['scores'][0]      # e.g., 0.92
```

### Batch Processing with Memory Awareness

```python
# Source: Zilliz Vector Database + transformers docs
# https://zilliz.com/ai-faq/how-can-you-do-batch-processing-of-sentences-for-embedding-to-improve-throughput-when-using-sentence-transformers/

async def score_posts_batch(
    posts: list[Post],
    batch_size: int = 16
) -> dict[int, dict]:
    """Score posts in batches, memory-aware."""

    classifier = pipeline(...)  # Load once

    results = {}

    # Process in batches
    for i in range(0, len(posts), batch_size):
        batch = posts[i : i + batch_size]
        texts = [p.title + " " + p.body for p in batch]
        texts = [t[:2000] for t in texts]  # Truncate

        # Process batch
        for post, text in zip(batch, texts):
            result = classifier(text, ["positive", "negative", "neutral"])
            results[post.id] = {
                'label': result['labels'][0],
                'score': float(result['scores'][0])
            }

        # Log progress
        logger.info(f"Processed {min(i + batch_size, len(posts))}/{len(posts)}")

    return results
```

### PostgreSQL JSONB Aggregation Query

```sql
-- Source: https://neon.com/docs/functions/json_agg
-- Compute daily sentiment rollup with per-source breakdown

SELECT
    entity_id,
    DATE(published_at AT TIME ZONE 'UTC') as rollup_date,
    COUNT(*) as post_count,
    ROUND(AVG(sentiment_score)::numeric, 3) as sentiment_mean,
    jsonb_object_agg(
        source,
        jsonb_build_object(
            'mean', ROUND(AVG(sentiment_score)::numeric, 3),
            'count', COUNT(*),
            'min', ROUND(MIN(sentiment_score)::numeric, 3),
            'max', ROUND(MAX(sentiment_score)::numeric, 3)
        )
    ) as source_breakdown
FROM posts p
JOIN post_entity_mentions pem ON p.id = pem.post_id
WHERE pem.entity_id = $1
  AND DATE(published_at AT TIME ZONE 'UTC') = $2
  AND p.sentiment_score IS NOT NULL
GROUP BY pem.entity_id, DATE(published_at AT TIME ZONE 'UTC')
ORDER BY rollup_date DESC;
```

### SQLAlchemy Upsert with JSONB Breakdown

```python
# Source: SQLAlchemy 2.0 docs on insert().on_conflict_do_update()
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def upsert_sentiment_rollup(
    session: AsyncSession,
    entity_id: int,
    rollup_date: date,
    sentiment_mean: float,
    post_count: int,
    source_breakdown: dict  # e.g., {'hn': {'mean': 0.4, 'count': 12}, ...}
):
    """Upsert sentiment rollup. Create if new day, update if existing."""

    from db.models import SentimentRollup

    stmt = pg_insert(SentimentRollup).values(
        entity_id=entity_id,
        rollup_date=rollup_date,
        sentiment_mean=sentiment_mean,
        post_count=post_count,
        source_breakdown=source_breakdown,
        updated_at=func.now()
    ).on_conflict_do_update(
        index_elements=['entity_id', 'rollup_date'],
        set_={
            'sentiment_mean': sentiment_mean,
            'post_count': post_count,
            'source_breakdown': source_breakdown,
            'updated_at': func.now()
        }
    )

    await session.execute(stmt)
    await session.commit()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fine-tuned sentiment models (RoBERTa, DistilBERT) | Zero-shot classification (BART MNLI, GliClass, ModernBERT) | 2022-2023 | Zero-shot eliminates training bottleneck, enables new label sets without retraining. Trade-off: slightly lower accuracy, acceptable for Tier 1 (Tier 2 LLM refines). |
| Sentiment as single -1 to 1 score | Sentiment as (label, confidence) pair | 2023+ | Confidence enables downstream routing (Tier 2 processes only low-confidence posts). Single score loses this signal. |
| Hourly + daily rollups | Daily only (or hourly if real-time needed) | 2024+ | Daily matches typical business cycles, hourly creates sparse data. With 6-hour collection, daily is natural boundary. |
| Application-side aggregation | Database-side JSONB aggregation | 2021+ (PostgreSQL 13+) | Database aggregation is orders of magnitude faster, simpler to reason about, enables indexing. |

**Deprecated/outdated:**
- AskNews API for sentiment (Phase 5): Replaced with own pipeline (Phase 6 collection + Phase 7 scoring)
- v1.0 SentimentTimeseries table: Replaced entirely with new SentimentRollup table in Phase 7 (breaking change, acceptable for v2.0 fresh start)
- RoBERTa fine-tuning: GliClass zero-shot avoids training entirely; only fine-tune if accuracy gaps emerge in production

## Open Questions

1. **Exact sentiment label encoding: label string vs numeric?**
   - What we know: User wants label + confidence stored; Tier 2 LLM will use label to route aspect extraction.
   - What's unclear: Should Post.sentiment_label store 'Positive'/'Negative'/'Neutral' (strings) or map to integers (0/1/2) for space efficiency?
   - Recommendation: Store strings. Strings are self-documenting in logs and easier to debug. Space difference negligible (~10 bytes per 1M posts).

2. **Batch size calibration for memory budget?**
   - What we know: batch_size=16 at 512 tokens ≈ 100-150MB GPU memory; Render has 1.5GB total, other processes use ~500MB.
   - What's unclear: Exact overhead of transformers.pipeline() wrapper + inference batch lookup overhead.
   - Recommendation: Start batch_size=8 (conservative), benchmark on production Render instance during first run, increase to 16-32 if memory stays <1.0GB.

3. **Should sentiment rollup table include hourly granularity?**
   - What we know: User chose daily only initially; 6-hour collection cycle makes daily natural.
   - What's unclear: Frontend requirement — does UI show hourly charts or daily only?
   - Recommendation: Defer hourly to Phase 8/Tier 2. Start with daily. API can artificially "hourly-ize" by resampling daily data if needed later.

4. **Entity list endpoint: include latest_sentiment_score or leave minimal?**
   - What we know: Phase 6 completed entity listing; CONTEXT.md marked this as Claude's discretion.
   - What's unclear: Frontend demand — does entity list show sentiment badge, or is that only in detail view?
   - Recommendation: Defer to frontend discussion. Minimal variant (no sentiment on list) is simpler; add sentiment if frontend explicitly requests it later.

## Validation Architecture

> Skipped: workflow.nyquist_validation is not enabled in .planning/config.json. Test infrastructure to be created in Wave 0 of implementation if needed.

## Sources

### Primary (HIGH confidence)
- [Hugging Face Zero-Shot Classification](https://huggingface.co/tasks/zero-shot-classification) - Pipeline interface, model recommendations
- [Hugging Face Transformers Pipelines Docs](https://huggingface.co/docs/transformers/main_classes/pipelines) - Pipeline API, device management
- [Knowledgator/GLiClass GitHub](https://github.com/Knowledgator/GLiClass) - Architecture, performance characteristics, zero-shot setup
- [PostgreSQL JSONB Functions Docs](https://www.postgresql.org/docs/current/functions-json.html) - jsonb_object_agg, jsonb_build_object

### Secondary (MEDIUM confidence)
- [Zilliz - Batch Processing with Sentence Transformers](https://zilliz.com/ai-faq/how-can-you-do-batch-processing-of-sentences-for-embedding-to-improve-throughput-when-using-sentence-transformers/) - Memory optimization, batch sizing patterns
- [Neon - PostgreSQL JSONB Aggregation](https://neon.com/docs/functions/json_agg) - JSONB aggregation best practices, examples
- [Milvus - Sentence Transformer Inference Optimization](https://milvus.io/ai-quick-reference/how-can-you-reduce-the-memory-footprint-of-sentence-transformer-models-during-inference-or-when-handling-large-numbers-of-embeddings) - Memory footprint reduction strategies

### Tertiary (reference)
- [AWS - PostgreSQL as JSON Database](https://aws.amazon.com/blogs/database/postgresql-as-a-json-database-advanced-patterns-and-best-practices/) - Advanced JSONB patterns, indexing strategies

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Hugging Face transformers and PostgreSQL JSONB are industry standard; zero-shot classification is well-documented and actively maintained
- Architecture: HIGH - Pipeline chaining pattern is straightforward; JSONB aggregation pattern is proven PostgreSQL technique
- Pitfalls: MEDIUM-HIGH - Model loading, batch sizing, and OOM are real issues with transformers, but solutions are well-documented. JSONB edge cases (null handling) less common in practice.

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (30 days; transformers and zero-shot classification are stable domain, GliClass model updates slow)
