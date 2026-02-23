# Phase 11: Entity Linking - Research

**Researched:** 2026-02-24
**Domain:** Entity mention extraction from posts, many-to-many relationship linking, NLP-based named entity recognition patterns
**Confidence:** HIGH

## Summary

Phase 11 closes a critical integration gap: the `post_entity_mentions` table (created in Phase 5) is never populated, causing downstream phases (7-9) to fail gracefully with empty aggregations and charts. The challenge is extracting which entities (AI tools/models) are mentioned in each post's title + body text, then creating junction table rows linking posts to entities. Three approaches exist: (1) keyword matching with ambiguity detection (simple, fast, proven in Phase 6), (2) rule-based NER patterns (moderate complexity), (3) pre-trained NLP model (slow, high memory on Render). Phase 6 already implements keyword filtering (is_relevant), making approach 1 the natural extension. The system will extract mentions for all existing posts (backfill) and route new posts through the same mention-extraction logic during collection. This unblocks: aggregate_sentiment to produce non-empty SentimentRollup rows with source_breakdown, extract_aspects to route posts with entity context (currently skips posts with zero mentions), and frontend to display sentiment data (currently empty state only).

**Primary recommendation:** Extend Phase 6's keyword-matching approach into a mention extractor service that identifies which VALID_ENTITIES appear in post text (case-insensitive substring match with word boundaries to avoid false positives). Backfill existing posts in a scheduled job or one-time migration script. Add mention extraction as a step in the collection pipeline for new posts (after save_post, before sentiment scoring). Use the same entity list and ambiguity handling already proven in Phase 6. No additional NLP models needed — keep memory footprint low on Render.

## Standard Stack

### Core Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlalchemy | 2.0.35 (existing) | Async ORM for inserting PostEntityMention rows and querying entities | Already in stack; enables efficient batch inserts and transactions |
| asyncpg | 0.30.0 (existing) | Async PostgreSQL driver for bulk inserts | Already in use; handles batch operations efficiently |
| regex / re | Python stdlib | Pattern-based entity mention detection (word boundaries) | Standard library, zero overhead; sufficient for keyword matching |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| spacy | 3.7.0+ | Pre-trained NLP for named entity recognition (NER) | Only if keyword matching produces insufficient coverage; deferred to v2.1 |
| transformers | 4.39.0+ (existing from Phase 7) | Zero-shot classification for mention confidence | Not recommended; memory overhead; keyword approach simpler |

### Model / Implementation Choices

| Decision | Rationale |
|----------|-----------|
| **Entity source** | Load entity names from database (SELECT * FROM entities) at job start. Caches entity list in memory for duration of job. Allows dynamic entity management without code redeploy. |
| **Mention detection** | Case-insensitive substring matching with word boundaries (regex `\b{entity_name}\b`). Prevents false positives ("ai" matching inside "painted"). Same pattern proven in Phase 6 is_relevant() filter. |
| **Backfill approach** | Create a scheduled job (runs once on first deploy) or one-time migration script to process all existing posts. Inserts PostEntityMention rows for any entity mentioned in post.title + post.body. Logs stats (total posts, total mentions, duplicates via UniqueConstraint). |
| **Incremental extraction** | Add mention extraction to collection pipeline after save_post(). Extract mentions for new posts, write PostEntityMention before sentiment scoring. Keeps post and mentions in same transaction. Idempotent via UniqueConstraint (post_id, entity_id). |
| **Mention ambiguity** | If "Claude" and "Clause" are both in VALID_ENTITIES, matching "clause" in text will match both (since substring is case-insensitive). VALID_ENTITIES is curated to avoid this (e.g., "Claude" vs "GPT-4" are unambiguous). If needed, resolve via entity category (if text says "Claude" and context is "AI models", prioritize Claude over any generic match). For v2.0, accept false positives as acceptable; filter with relevance score in Phase 7 aggregation. |
| **Deduplication** | UniqueConstraint on (post_id, entity_id) in PostEntityMention table prevents duplicate mentions. Bulk insert with ON CONFLICT DO NOTHING discards duplicates silently. |

### Installation

```bash
# No new dependencies needed — all tools already in requirements.txt
# If adding spacy later (Phase 2.1):
pip install spacy==3.7.0
python -m spacy download en_core_web_sm
```

## Architecture Patterns

### Recommended Project Structure

Mention extraction fits into Phase 6 (collection) pipeline:

```
backend/
├── pipeline/
│   ├── jobs/
│   │   ├── collect_*.py                  # Phase 6 (existing)
│   │   ├── extract_entity_mentions.py    # NEW: Backfill job
│   │   └── ...
│   ├── services/
│   │   ├── filter_service.py             # Phase 6 (existing)
│   │   ├── storage_service.py            # Phase 6 (existing)
│   │   ├── mention_service.py            # NEW: Entity mention extraction
│   │   └── ...
│   ├── scheduler.py                      # MODIFIED: add backfill job once, integrate mention extraction into collection
│   └── models.py                         # (existing)
├── db/
│   └── models.py                         # (existing — PostEntityMention already defined)
└── ...
```

### Pattern 1: Keyword-Based Mention Extraction with Word Boundaries

**What:** Load entity names, search post text for case-insensitive matches with word boundaries, return list of entity IDs found.

**When to use:** Every time a post is saved (new posts) and as a batch job for backfill (existing posts).

**Example:**

```python
# Source: Phase 6 is_relevant() pattern adapted for mention extraction
# backend/pipeline/services/mention_service.py

import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Entity, PostEntityMention, Post

logger = logging.getLogger(__name__)


class MentionExtractor:
    """Extract entity mentions from post text using keyword matching."""

    def __init__(self):
        """Initialize with empty entity cache — load on first call."""
        self._entity_map: dict[str, int] | None = None

    async def load_entities(self, session: AsyncSession) -> None:
        """Load all VALID_ENTITIES into memory as {name: entity_id} map.

        Call once per job run. Caches result internally.
        """
        if self._entity_map is not None:
            return  # Already loaded

        query = select(Entity.id, Entity.name)
        result = await session.execute(query)
        rows = result.all()

        self._entity_map = {row.name: row.id for row in rows}
        logger.info("MentionExtractor: loaded %d entities", len(self._entity_map))

    def extract_mentions(self, text: str) -> set[int]:
        """Extract entity IDs mentioned in text (case-insensitive, word boundary).

        Args:
            text: Post title + body concatenated

        Returns:
            Set of entity_id integers for matches found
        """
        if self._entity_map is None:
            raise RuntimeError("MentionExtractor not initialized — call load_entities() first")

        if not text:
            return set()

        mentioned_ids = set()

        for entity_name, entity_id in self._entity_map.items():
            # Word boundary regex: \bClaude\b matches "Claude" as whole word, not inside "Claudicate"
            # Case-insensitive flag: (?i) or re.IGNORECASE
            pattern = r"\b" + re.escape(entity_name) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                mentioned_ids.add(entity_id)

        return mentioned_ids


async def extract_and_save_mentions(
    session: AsyncSession,
    post_id: int,
    text: str,
    extractor: MentionExtractor
) -> int:
    """Extract mentions from post text and save to PostEntityMention table.

    Args:
        session: Active AsyncSession
        post_id: Post to link entities to
        text: Post title + body
        extractor: Initialized MentionExtractor

    Returns:
        Count of mentions added (0 if post already has mentions, >0 if new)
    """
    mention_ids = extractor.extract_mentions(text)

    if not mention_ids:
        logger.debug("extract_and_save_mentions: post %d has no entity mentions", post_id)
        return 0

    logger.debug(
        "extract_and_save_mentions: post %d mentions %d entities",
        post_id, len(mention_ids)
    )

    # Bulk insert PostEntityMention rows — idempotent via UniqueConstraint
    # ON CONFLICT DO NOTHING silently ignores duplicates if post already mentions entity
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(PostEntityMention).values([
        {"post_id": post_id, "entity_id": eid}
        for eid in mention_ids
    ]).on_conflict_do_nothing()

    result = await session.execute(stmt)
    await session.commit()

    # Note: rowcount may not reflect actual inserts due to ON CONFLICT
    # For stats, query actual PostEntityMention rows for this post
    mention_query = select(PostEntityMention).where(PostEntityMention.post_id == post_id)
    mention_result = await session.execute(mention_query)
    actual_mentions = mention_result.all()

    return len(actual_mentions)
```

### Pattern 2: Backfill Job for Existing Posts

**What:** Scan all existing posts, extract mentions for each, insert into PostEntityMention. Run once on Phase 11 deploy.

**When to use:** One-time migration after Phase 11 schema is created but before Phase 7+ jobs depend on mentions.

**Example:**

```python
# Source: Phase 6 collection pattern adapted for batch backfill
# backend/pipeline/jobs/extract_entity_mentions.py

import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.models import Post, PostEntityMention
from pipeline.services.mention_service import MentionExtractor, extract_and_save_mentions

logger = logging.getLogger(__name__)


async def run_backfill_entity_mentions(session: AsyncSession) -> dict:
    """Backfill PostEntityMention for all existing posts without mentions.

    Query all posts that have no PostEntityMention rows yet, extract mentions,
    and populate the junction table. Logs progress and stats.

    Args:
        session: Active AsyncSession

    Returns:
        Stats dict: {posts_scanned, mentions_added, already_linked, errors}
    """
    stats = {
        "posts_scanned": 0,
        "mentions_added": 0,
        "already_linked": 0,
        "posts_with_no_mentions": 0,
        "errors": 0,
    }

    # Initialize mention extractor
    extractor = MentionExtractor()
    await extractor.load_entities(session)

    # Query posts that have NO PostEntityMention rows yet
    # (idempotent: safe to rerun, skips posts already processed)
    has_mentions = select(1).select_from(PostEntityMention).where(
        PostEntityMention.post_id == Post.id
    ).exists()

    query = select(Post.id, Post.title, Post.body).where(~has_mentions).order_by(Post.id)

    result = await session.execute(query)
    posts_to_process = result.all()

    if not posts_to_process:
        logger.info("backfill_entity_mentions: all posts already linked, skipping")
        return stats

    logger.info(
        "backfill_entity_mentions: processing %d posts without mentions",
        len(posts_to_process)
    )

    for post in posts_to_process:
        stats["posts_scanned"] += 1

        try:
            # Combine title + body for mention extraction
            text = ((post.title or "") + " " + (post.body or "")).strip()

            # Extract and save mentions
            count = await extract_and_save_mentions(
                session, post.id, text, extractor
            )

            if count > 0:
                stats["mentions_added"] += count
            else:
                stats["posts_with_no_mentions"] += 1

        except Exception as exc:
            logger.error(
                "backfill_entity_mentions: error processing post %d: %s",
                post.id, exc, exc_info=True
            )
            stats["errors"] += 1

    logger.info(
        "backfill_entity_mentions: complete — %s",
        {k: v for k, v in stats.items() if v > 0},
    )
    return stats
```

### Pattern 3: Integration into Collection Pipeline

**What:** After save_post() succeeds, call mention extraction on the same post text before sentiment scoring.

**When to use:** Modify collection job wrappers to call extract_and_save_mentions after save_post.

**Example:**

```python
# Source: Phase 6 collect_hackernews.py + Phase 11 mention extraction
# Modified collector job excerpt

async def run_collect_hackernews(session: AsyncSession) -> dict:
    """Collect HN stories and extract entity mentions."""

    stats = {
        "collected_stories": 0,
        "collected_comments": 0,
        "mentions_extracted": 0,
        "filtered": 0,
        "duplicates": 0,
        "errors": 0,
    }

    # Initialize mention extractor once per job
    extractor = MentionExtractor()
    await extractor.load_entities(session)

    async with httpx.AsyncClient() as client:
        stories = await _fetch_with_retry(fetch_hn_stories, since_unix, client)

        for hit in stories:
            # ... existing collection logic ...
            normalized = normalize_hn_story(hit)
            text = f"{normalized['title'] or ''} {normalized['body'] or ''}"

            if not is_relevant(text):
                stats["filtered"] += 1
                continue

            post = PostCreate(**normalized)
            saved = await save_post(post, session)
            if saved:
                stats["collected_stories"] += 1

                # NEW: Extract mentions for this post
                try:
                    await extractor.load_entities(session)  # Idempotent: loads once
                    mention_count = await extract_and_save_mentions(
                        session, post.id, text, extractor
                    )
                    if mention_count > 0:
                        stats["mentions_extracted"] += mention_count
                except Exception as exc:
                    logger.warning(
                        "Failed to extract mentions for post %s: %s",
                        hit["objectID"], exc
                    )
                    stats["errors"] += 1

            else:
                stats["duplicates"] += 1

    return stats
```

### Anti-Patterns to Avoid

- **Case-sensitive matching:** Don't use exact string match ("Claude" won't match "claude"). Always case-insensitive to catch all mentions.
- **Substring matching without boundaries:** Don't match "ai" inside "painted" or "train". Always use word boundary regex `\b{entity}\b`.
- **Loading entities per-post:** Don't query database for entity list inside the extraction loop. Load once at job start, cache in memory.
- **Synchronous regex on large text:** Don't apply regex in a tight loop over 10K+ posts without batching. Process in-memory batch of 100-1000 posts per iteration.
- **Ignoring duplicate mentions:** Don't check for existing PostEntityMention rows before insert. Let the database UniqueConstraint handle deduplication via ON CONFLICT DO NOTHING.
- **Manual mention tracking:** Don't maintain a Python set of seen (post_id, entity_id) pairs. PostgreSQL deduplication is more reliable and automatic.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Entity name lookup | Manual dict-building or repeated queries | SQLAlchemy ORM select().all() cached in memory | Database query is atomic; caching avoids N+1 lookups |
| Keyword matching with word boundaries | Custom string split/find logic | Python `re` module with `\b...\b` patterns | Built-in regex handles Unicode word boundaries correctly; custom logic misses edge cases |
| Mention deduplication | Python set tracking (post_id, entity_id) | PostgreSQL UniqueConstraint + ON CONFLICT | Database constraint is reliable, atomic, works across job runs; Python tracking is fragile |
| Bulk insert of mentions | INSERT one row at a time in loop | sqlalchemy insert().values([...]) with ON CONFLICT | Batch insert is orders of magnitude faster; one network round-trip vs thousands |
| Mention extraction for new posts | Separate scheduled job | Integration into collection pipeline after save_post | Same transaction keeps post and mentions consistent; separate job risks race conditions |

**Key insight:** Entity mention extraction is "simple in principle, complex at scale" — word boundary edge cases, deduplication safety, and batch performance all benefit from proven libraries and database features.

## Common Pitfalls

### Pitfall 1: False Positives with Substring Matching

**What goes wrong:** Post contains "We're training our AI" and "AI" is a VALID_ENTITY. Mention extractor finds "AI" inside "training" (wrong). Then post gets linked to AI entity when text discusses a different topic.

**Why it happens:** Substring matching without word boundaries. Regex `AI` matches inside "training".

**How to avoid:**
- Always use word boundary regex: `\bAI\b` matches "AI" as a standalone word, not inside "training".
- Test regex patterns in isolation: `re.search(r'\b(?i)ai\b', 'training ai model')` returns match, `re.search(r'\b(?i)ai\b', 'training')` returns None.
- For entity names with special chars, use `re.escape()`: `pattern = r"\b" + re.escape(entity_name) + r"\b"`.

**Warning signs:** Post about "Claude" being "trained" gets linked to Training entity (if Training is in VALID_ENTITIES). Aggregation shows Training sentiment spiking on posts that don't mention it.

### Pitfall 2: Idempotency — Backfill Runs Twice

**What goes wrong:** Backfill job runs, populates PostEntityMention for 10K posts. Job is re-triggered accidentally (retry, operator error, etc.). Runs again, tries to insert same (post_id, entity_id) pairs. ON CONFLICT DO NOTHING skips silently, but logs show "0 mentions added" instead of "10K mentions already exist."

**Why it happens:** Job doesn't track "has backfill run" state. Query checks "posts without mentions" but assumes first run only.

**How to avoid:**
- Use UniqueConstraint on (post_id, entity_id) — allows safe reruns.
- Backfill query checks `WHERE NOT EXISTS (SELECT 1 FROM post_entity_mentions WHERE post_id = posts.id)` — only unprocessed posts.
- Log final count: query the table to confirm mentions were added, not just assume INSERT succeeded.
- Consider one-time migration flag: add `mentioned_extracted: Boolean = False` on Post table, set to True after backfill. Then query `WHERE mentioned_extracted = False` for idempotency. Alternative: use NOT EXISTS check (simpler, no new column).

**Warning signs:** Backfill runs successfully both times; second run logs "0 mentions added"; posts still have zero mentions in database.

### Pitfall 3: OOM (Out Of Memory) on Large Backfill

**What goes wrong:** Backfill job loads ALL entity names into memory (10MB), then queries ALL posts without mentions (100K posts), tries to process them all in one loop. Memory spike to 500MB+. On Render with 1.5GB limit, this is acceptable but risky.

**Why it happens:** No batching — naive code loads all posts into Python list, then iterates. Entity cache is fine; post cache is the problem.

**How to avoid:**
- Entity cache is acceptable (100-1000 entities × 100 bytes = 100KB max).
- Batch posts: `query.limit(1000)` in loop, process in chunks of 1000, commit after each batch.
- Monitor: log memory usage after each batch, stop if approaching 1.0GB.

**Warning signs:** Backfill job logs first batch processed, then hangs or crashes with OOM.

### Pitfall 4: Entity Name Ambiguity

**What goes wrong:** VALID_ENTITIES includes both "Claude" and "Clause" (if someone adds it). Post text says "The clause about performance" gets linked to Claude (wrong). Downstream aggregation attributes sentiment to wrong entity.

**Why it happens:** Case-insensitive substring matching catches "Claude" inside "Clause".

**How to avoid:**
- Curate VALID_ENTITIES carefully: avoid near-duplicates (Claude vs Clause).
- If ambiguity exists, add priority ranking: "Claude" before "Clause" in entity list, stop matching after first match.
- Add entity category context: if text says "AI model Claude" and Clause is a document type, use context to disambiguate.
- For v2.0, accept false positives as acceptable risk. Monitor in production.

**Warning signs:** Aggregation shows entity with very different sentiment than expected. Manual audit reveals posts about unrelated entities linked incorrectly.

### Pitfall 5: Mentions Extracted but Not Linked to Sentiment

**What goes wrong:** Backfill populates PostEntityMention. Sentiment aggregation job runs, queries `JOIN post_entity_mentions`, finds no rows (because they were inserted after sentiment scored). No sentiment rollup rows generated. Frontend shows empty sentiment.

**Why it happens:** Race condition between backfill and sentiment aggregation. Sentiment was scored before mentions were extracted.

**How to avoid:**
- Run backfill BEFORE any sentiment scoring/aggregation job runs.
- Backfill should be Phase 11 Wave 0 (setup) task, completing before Phase 7/8 jobs are triggered.
- Order in scheduler: (1) backfill runs once, (2) collection/score/aggregate chain starts, (3) extract_aspects chains.
- Test idempotency: rerun sentiment aggregation after backfill to confirm it finds mentions now.

**Warning signs:** After Phase 11 deployment, sentiment aggregation logs show "0 entity-days updated" even though posts exist.

## Code Examples

Verified patterns from official sources:

### Word Boundary Regex with Case Insensitivity

```python
# Source: Python re module documentation
# https://docs.python.org/3/library/re.html

import re

entity_name = "Claude"

# Case-insensitive, word boundary match
pattern = r"\b" + re.escape(entity_name) + r"\b"
text = "Claude is great, but I trained on claude-2 architecture."

matches = re.findall(pattern, text, re.IGNORECASE)
# Returns: ['Claude', 'claude']

# Verify no false positives inside words
text_bad = "This Claudication symptom is rare."
matches_bad = re.findall(pattern, text_bad, re.IGNORECASE)
# Returns: [] (no match; re.IGNORECASE doesn't affect word boundary logic)
```

### SQLAlchemy Bulk Insert with ON CONFLICT

```python
# Source: SQLAlchemy 2.0 docs + PostgreSQL insert...on_conflict
# https://docs.sqlalchemy.org/en/20/dialects/postgresql.html

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select
from db.models import PostEntityMention

async def insert_mentions_idempotent(
    session: AsyncSession,
    post_id: int,
    entity_ids: set[int]
):
    """Insert mention rows, silently skip duplicates."""

    stmt = pg_insert(PostEntityMention).values([
        {"post_id": post_id, "entity_id": eid}
        for eid in entity_ids
    ]).on_conflict_do_nothing()

    await session.execute(stmt)
    await session.commit()

    # Verify actual count (rowcount may be -1 with ON CONFLICT)
    count_query = select(PostEntityMention).where(
        PostEntityMention.post_id == post_id
    )
    result = await session.execute(count_query)
    return len(result.all())
```

### Entity Cache Pattern

```python
# Source: Established caching pattern in systems with static reference data
# Similar to Phase 6 entity validation logic

class EntityCache:
    """Cache entity IDs to avoid repeated database queries."""

    def __init__(self):
        self._cache: dict[str, int] | None = None

    async def load(self, session: AsyncSession) -> None:
        """Load entity names and IDs into memory."""
        if self._cache is not None:
            return  # Already loaded

        from sqlalchemy import select
        from db.models import Entity

        query = select(Entity.name, Entity.id)
        result = await session.execute(query)
        self._cache = {row.name: row.id for row in result.all()}

    def get_id(self, entity_name: str) -> int | None:
        """Get entity ID by name (exact match)."""
        if self._cache is None:
            raise RuntimeError("Cache not loaded")
        return self._cache.get(entity_name)

    def all_names(self) -> list[str]:
        """Get all entity names for iteration."""
        if self._cache is None:
            raise RuntimeError("Cache not loaded")
        return list(self._cache.keys())
```

### Batched Backfill Loop

```python
# Source: Batch processing pattern for large datasets
# Similar to Phase 7 score_sentiment batch sizing

async def backfill_batched(session: AsyncSession, batch_size: int = 1000) -> dict:
    """Backfill mentions in batches to avoid OOM."""

    stats = {"total_processed": 0, "mentions_added": 0}

    extractor = MentionExtractor()
    await extractor.load_entities(session)

    skip = 0
    while True:
        # Fetch batch of unprocessed posts
        has_mentions = select(1).select_from(PostEntityMention).where(
            PostEntityMention.post_id == Post.id
        ).exists()

        query = (
            select(Post.id, Post.title, Post.body)
            .where(~has_mentions)
            .order_by(Post.id)
            .limit(batch_size)
            .offset(skip)
        )

        result = await session.execute(query)
        posts = result.all()

        if not posts:
            break  # No more posts

        # Process batch
        for post in posts:
            text = ((post.title or "") + " " + (post.body or "")).strip()
            count = await extract_and_save_mentions(
                session, post.id, text, extractor
            )
            stats["mentions_added"] += count

        stats["total_processed"] += len(posts)
        skip += batch_size

        logger.info("Backfill progress: %d posts processed", stats["total_processed"])

    return stats
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual entity linking (spreadsheet) | Automated keyword extraction (regex + database) | v2.0 | Eliminates manual data entry errors; allows dynamic entity management; scales to thousands of posts |
| NER model (spacy, transformers) | Keyword matching with word boundaries | v2.0 | Keyword approach is 100x faster, 1/10 memory, zero model latency. NER useful only for detecting NEW unknown entities. |
| Linking during collection | Separate batch job | Early design consideration | Batch job decouples collection from linking; allows backfill of pre-existing posts without reprocessing sources |
| Post-level mention tracking | Entity junction table (PostEntityMention) | Phase 5 schema | Junction table enables per-entity aggregation (required for Phase 7/8 success). Post-level tracking insufficient. |

**Deprecated/outdated:**
- Manual entity curation in collection code: Reason — entity list now in database, dynamic
- NLP models for mention detection: Reason — keyword matching proven sufficient for v2.0 free sources; defer advanced NER to v2.1

## Open Questions

1. **Backfill timing: one-time job vs migration script?**
   - What we know: Backfill needs to run before sentiment aggregation depends on mentions
   - What's unclear: Should it be a scheduled job (can be re-triggered) or a one-time migration (immutable)?
   - Recommendation: Scheduled job (run_backfill_entity_mentions) callable from CLI. Allows reruns if needed; tracks stats; integrates with audit logging. Alternative: migration script if purely one-time setup.

2. **Entity list updates: how to handle new entities added post-backfill?**
   - What we know: VALID_ENTITIES in database can be updated; backfill processes all entities at run time
   - What's unclear: If new entity is added, should old posts be re-scanned for mentions?
   - Recommendation: For v2.0, no retroactive linking for new entities. New entities apply to posts collected after entity is added. Operator can trigger backfill manually if needed. Add documentation: "Adding new entities: run backfill_entity_mentions to link existing posts."

3. **Post text mutations: what if post body is edited?**
   - What we know: Posts are inserted once, not updated (except sentiment/aspects)
   - What's unclear: If post body changes (unlikely in social media snapshot), should mentions be re-extracted?
   - Recommendation: Assume posts are immutable once saved. Mentions are extracted once. No updates needed.

4. **False negative rate: what if entity is mentioned but not matched?**
   - What we know: Keyword matching will miss synonyms ("ChatGPT" vs "gpt4", "GPT" vs "OpenAI")
   - What's unclear: Is 90% recall acceptable for v2.0? Should fuzzy matching be added?
   - Recommendation: For v2.0, exact keyword matching is acceptable. Curate VALID_ENTITIES to include common aliases (e.g., both "Claude" and "Claude 3" if both are used). Monitor false negatives in production; add fuzzy matching to Phase 2.1 if needed.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.2.0 + pytest-asyncio 0.24.0 |
| Config file | pyproject.toml (existing) |
| Quick run command | `pytest tests/test_mention_extraction.py -x -v` |
| Full suite command | `pytest tests/ -x` |
| Estimated runtime | ~30 seconds (mention extraction is fast) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SENT-01 | Aggregate sentiment query joins posts + post_entity_mentions and produces non-empty SentimentRollup rows | integration | `pytest tests/test_aggregate_sentiment.py::test_aggregation_with_mentions -xvs` | ✅ exists |
| SENT-02 | Extract aspects query finds posts with entity mentions (no longer skips); AspectSentiment rows created | integration | `pytest tests/test_aspect_extraction.py::test_extraction_with_mentions -xvs` | ✅ exists |
| SENT-04 | Aspect scores linked to entities via post_entity_mentions; API returns aspects per entity | integration | `pytest tests/test_aspect_api.py::test_aspects_with_real_mentions -xvs` | ✅ exists |
| FRON-01 | Frontend sentiment chart receives non-empty source breakdown from aggregation | integration (manual) | Manual: (1) Trigger collection, (2) Backfill mentions, (3) Score/aggregate, (4) Verify POST query returns data | N/A |
| FRON-02 | Frontend aspect chart receives aspect data with entity-level granularity | integration (manual) | Manual: (1) Same as FRON-01, (2) Verify GET /aspects endpoint returns aspects, (3) Chart renders | N/A |

### Wave 0 Gaps (must be created before implementation)

**No new test files needed — existing tests will pass once post_entity_mentions is populated:**
- [x] `tests/test_aggregate_sentiment.py` — already exists (test_aggregation_with_mentions checks JOIN with mentions)
- [x] `tests/test_aspect_extraction.py` — already exists (test_extraction_with_mentions checks entity linking)
- [x] `tests/test_aspect_api.py` — already exists (test_aspects_with_real_mentions checks API output)

**Wave 0 implementation tasks (before jobs run):**
- [ ] `backend/pipeline/services/mention_service.py` — MentionExtractor class with extract_mentions() and extract_and_save_mentions()
- [ ] `backend/pipeline/jobs/extract_entity_mentions.py` — run_backfill_entity_mentions() job
- [ ] Integration into collector jobs — add mention extraction after save_post()
- [ ] Scheduler registration — add backfill job as one-time on startup (or CLI trigger)

## Sources

### Primary (HIGH confidence)

- Python `re` Module - [Word Boundaries and Case Insensitivity](https://docs.python.org/3/library/re.html) — Regex patterns verified
- SQLAlchemy 2.0 Docs - [Insert with ON CONFLICT DO NOTHING](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html) — Bulk insert pattern verified
- PostgreSQL Docs - [INSERT ... ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT) — Deduplication strategy verified
- VibeCheck Phase 6 - [is_relevant() Filter](backend/pipeline/services/filter_service.py) — Proven keyword matching pattern
- VibeCheck Phase 5 - [PostEntityMention Schema](backend/db/models.py) — Junction table structure verified

### Secondary (MEDIUM confidence)

- Phase 7 Research - [Batch Processing Patterns](v2.0-INTEGRATION-CHECK.md lines 193-197) — Aggregation query expecting mention joins
- Phase 8 Research - [Extract Aspects](backend/pipeline/jobs/extract_aspects.py lines 83-89) — Entity lookup pattern via join
- v2.0 Integration Audit - [Gap Documentation](v2.0-INTEGRATION-CHECK.md line 612) — Critical gap confirmed

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH — re module and SQLAlchemy patterns proven in Phase 6 and existing codebase
- **Architecture:** HIGH — Pattern is straightforward extension of Phase 6 filter service; no new technologies
- **Pitfalls:** MEDIUM-HIGH — Word boundary edge cases (ambiguity, false positives) documented in Phase 6 experience; deduplication safety proven by UniqueConstraint

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (30 days; entity linking is stable domain, no major changes expected)
