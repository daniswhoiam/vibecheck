# Feature Research

**Domain:** Free data source ingestion + two-tier sentiment pipeline for developer sentiment tracker
**Researched:** 2026-02-19
**Confidence:** HIGH (primary sources: official API docs, Hugging Face model cards, sentiment_analysis_improvement.md)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features v2.0 must have. Missing any of these = the AskNews replacement is incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Common Post Schema | Without a unified schema, all 5 collectors write different data shapes; downstream pipeline fragments into 5 separate code paths | LOW | Should be the first implementation; normalize source, url, title, body, author, created_at, content_hash from all sources |
| Storage schema migration | Current schema stores `reddit_sentiment` on `SentimentTimeseries`; new pipeline needs `posts`, `tool_mentions`, `sentiment_scores` tables | HIGH | Alembic migrations already in place; existing `SentimentTimeseries` table must be preserved for backward compat |
| HN Algolia collector | Replaces AskNews; highest-signal free source for developer discourse; no auth required | LOW | `search_by_date` + `tags=comment` + `numericFilters=points>2`; 1,000-hit pagination cap per query — use `created_at_i` range filtering to avoid cap; ~10K req/hr |
| Reddit PRAW collector | Replaces AskNews Reddit data; r/LocalLLaMA, r/cursor, r/copilot, r/ChatGPT, r/vscode are highest-signal | MEDIUM | Free tier: 100 QPM with OAuth; PRAW handles rate limiting automatically; 1,000-post per-listing ceiling; non-commercial use only per Reddit ToS |
| Keyword relevance filter | Raw API output is ~70-80% irrelevant; must filter before hitting sentiment pipeline | LOW | Match tool names (Copilot, Cursor, Windsurf, Cody, Tabnine, Continue, Aider, Claude Code, Devin, Supermaven, Amazon Q) plus contextual terms; negative keywords for false positives ("airline copilot", "database cursor"); runs in microseconds |
| Content deduplication (URL hash) | Same posts surface across platforms; double-counting skews sentiment | LOW | Extend existing `deduplication_service.py` SHA-256 URL hash pattern to new `posts` table; add content body hash as secondary check |
| Tier 1 RoBERTa sentiment classifier | Replaces AskNews pre-computed sentiment; all posts need classification | MEDIUM | `cardiffnlp/twitter-roberta-base-sentiment-latest`; 3-class output (positive/neutral/negative); ~10-20 texts/sec CPU; load once at startup; known limitation: struggles with sarcasm and technical jargon |
| REST API backward compatibility | Frontend currently consumes entity endpoints, sparklines, cursor-paginated sentiment history | LOW | New schema must preserve existing API contract; don't break the frontend during migration |

### Differentiators (Competitive Advantage)

Features that make v2.0 meaningfully better than v1.0 or generic social listening tools.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Tier 2 LLM extraction (GPT-4o-mini) | Structured aspect-level sentiment with sarcasm detection, tool attribution, comparative flags — impossible with RoBERTa alone | HIGH | Routes only ~30-40% of posts (non-neutral or low-confidence from Tier 1); $0.15/M input + $0.60/M output; use `.beta.chat.completions.parse()` with Pydantic model for 100% valid JSON; estimated $20-30/mo at 5,000 posts/day |
| Aspect-level sentiment extraction | Per-tool scores for performance, cost, code quality, reliability, UX, speed, context window | HIGH | Only Tier 2 provides this; no pre-trained ABSA model exists for developer text; Pydantic schema: `AspectSentiment(performance, cost_pricing, code_quality, reliability, ux_developer_experience, speed_latency, context_window)` |
| Embedding-based relevance filter (Stage 2) | Catches semantically relevant posts that miss keyword matching ("my autocomplete keeps hallucinating" without naming a tool) | MEDIUM | `sentence-transformers/all-MiniLM-L6-v2`; 384-dim vectors; 14,200 sentences/sec; cosine similarity threshold 0.35-0.45 against 30-50 reference queries; 22MB model footprint |
| Discourse collector (forum.cursor.com) | High signal-to-noise; Cursor forum is on-topic by definition; overlooked source with rich user feedback | MEDIUM | REST API at `/latest.json`, `/t/{id}.json`; rate limits instance-configured (not published); use 1 req/sec conservative default; poll every 60 minutes |
| Dev.to collector | Blog-style opinion pieces with tag-based filtering; different tone from HN/Reddit comments | LOW | Use v1 API (v0 deprecated); `GET /api/articles?tag=ai&per_page=30`; no auth required for reads; tags: `ai`, `cursor`, `copilot`, `llm`, `github-copilot` |
| Per-source sentiment breakdown | Distinguish HN vs Reddit vs GitHub vs Discourse sentiment — different community biases | LOW | Requires `source` field on posts; frontend can filter and compare; no extra ML work if schema is right from the start |
| GitHub Issues collector | Bug frustrations and feature requests are direct user feedback; repos: getcursor/cursor, continuedev/continue, TabbyML/tabby | HIGH | REST API for Issues: 5,000 req/hr authenticated; poll every 60 minutes; GraphQL required for Discussions (deferred) |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Twitter/X integration | X is where tech discourse happens | Free tier: ~500 reads/month — essentially unusable for any polling; Basic tier: $200/month for 10K reads; developer discourse has migrated to HN/Reddit for technical discussion | Skip entirely; HN + Reddit cover the signal X used to provide for developer topics |
| Real-time webhooks for all sources | Feels more "live" than polling | HN has no webhook; Reddit public data webhooks are limited; Discourse webhooks require admin access to target forum; polling every 10-15 min is sufficient for a trend tracker | Poll HN/Reddit/Discourse; GitHub webhooks optional for tracked repos only |
| VADER or TextBlob as primary classifier | Zero cost, instant, no dependencies | VADER reads "Oh great, another hallucination" as positive; TextBlob scores "context window is 128K vs 200K" as neutral; neither handles sarcasm, technical jargon, or multi-entity comparisons | Use VADER/TextBlob only as ultra-fast pre-filter (rough score threshold gate before Tier 1 RoBERTa), never as primary classifier |
| Fine-tuned RoBERTa for developer text | Would improve Tier 1 accuracy on technical language | Requires 500-1,000 hand-labeled examples plus GPU training time; no existing labeled dataset for this domain; high effort for marginal gain vs just routing more to Tier 2 LLM | Defer fine-tuning until Tier 2 data accumulates enough labeled examples naturally |
| Separate vector database (Pinecone, Weaviate) | Embedding search "needs" a vector DB | Completely unnecessary at 1,000-10,000 posts/day; pgvector extension on existing PostgreSQL handles this trivially; adds infra complexity and cost | Add pgvector to existing PostgreSQL; no separate vector store needed at this scale |
| Celery/Redis task queue from the start | Production-grade async job processing | Massive operational overhead for a solo developer; requires Redis + separate worker processes + monitoring; APScheduler in-process is sufficient | Stay with APScheduler; graduate to `arq` (async Redis queue, FastAPI-native) only if job fanout becomes a real problem |
| Storing raw post text permanently | Enables full-text search and debugging | GDPR exposure for EU users; Reddit ToS requires deletion when users delete on Reddit; storage bloat | Store `evidence_quote` (short excerpts, 200-300 chars) with attribution links back to originals; aggregate into sentiment scores |
| GitHub Discussions in v2.0 | Rich qualitative community sentiment | GraphQL only — entirely different client pattern from REST; requires complex query construction; higher implementation cost for moderate additional signal | Defer to v2.2+; implement GitHub Issues (REST) first; Discussions are a separate, later feature |
| MinHash near-deduplication from day one | Catches cross-posted paraphrased content | `datasketch` library adds overhead; need to establish baseline first; exact URL hash dedup covers the common case | Start with SHA-256 URL + content hash (already in existing deduplication_service.py pattern); add MinHash only if cross-platform reposts are observed to be a problem |

---

## Feature Dependencies

```
[Common Post Schema]
    required-by --> [HN Algolia Collector]
    required-by --> [Reddit PRAW Collector]
    required-by --> [Discourse Collector]
    required-by --> [Dev.to Collector]
    required-by --> [GitHub Issues Collector]
                         feeds --> [Keyword Relevance Filter (Stage 1)]
                                       feeds --> [Embedding Relevance Filter (Stage 2)]
                                                     feeds --> [Content Deduplication]
                                                                   feeds --> [Tier 1 RoBERTa Classifier]
                                                                                 high-confidence-neutral --> [Storage]
                                                                                 low-confidence/opinionated --> [Tier 2 LLM Extraction]
                                                                                                                     produces --> [Aspect-Level Sentiment]
                                                                                                                     feeds --> [Storage]

[Storage Schema Migration]
    required-by --> [All Collectors] (new posts table)
    required-by --> [Tier 1 + Tier 2] (sentiment_scores, tool_mentions tables)
    must-preserve --> [REST API Backward Compatibility]

[Tier 2 LLM Extraction]
    requires --> [Tier 1 RoBERTa Classifier] (routing decision comes from Tier 1 output)
    requires --> [GPT-4o-mini API key] (or local Ollama as fallback)
    produces --> [Aspect-Level Sentiment] (only data source for aspect scores)

[GitHub Issues Collector]
    independent-of --> [HN/Reddit/Discourse/Dev.to] (different auth, different polling interval)
    uses-REST --> (no GraphQL needed for Issues)

[Embedding Relevance Filter]
    enhances --> [Keyword Relevance Filter] (catches semantic matches keyword filter misses)
    requires --> [sentence-transformers installed] (22MB model downloaded at startup)
    optional-in-MVP --> true (keyword filter alone is sufficient for v2.0 launch)
```

### Dependency Notes

- **Common Post Schema must be first:** Without a unified schema, each collector writes different data shapes into the pipeline. Every downstream component (filter, dedup, sentiment) would need source-specific handling. This is the single most important first step.
- **Keyword filter before embedding filter:** Embedding computation takes time; pre-filter with keywords first to avoid computing embeddings for 70-80% of posts that are clearly irrelevant. Stage 1 keywords → Stage 2 embeddings is the correct order.
- **Storage schema migration before any collector ships data:** New collectors write to new tables. Existing `SentimentTimeseries` stays for backward compat but new `posts`, `tool_mentions`, `sentiment_scores` tables are needed first.
- **Tier 1 required before Tier 2:** Tier 2 routing is based on Tier 1 confidence scores and polarity. Cannot route without Tier 1 output.
- **GitHub Issues is independent from other collectors:** Different auth pattern (personal access token), different polling interval (60 min), different data shape (no body text for issues, just title + comments). Can be a separate phase.
- **Aspect-level frontend display depends on Tier 2 data accumulation:** Cannot show meaningful aspect charts until weeks of Tier 2 extraction has run. Frontend evolution should be deferred until data exists.

---

## MVP Definition

This is the v2.0 milestone MVP — what must ship to replace AskNews at $0-50/mo.

### Launch With (v2.0 core)

- [ ] Common Post Schema — foundational; nothing else works without it
- [ ] Storage schema migration (posts + tool_mentions + sentiment_scores tables) — foundational
- [ ] HN Algolia collector — highest-signal free source; no auth; simplest to implement
- [ ] Reddit PRAW collector — second-highest signal; PRAW library handles complexity
- [ ] Keyword relevance filter — must have to avoid poisoning sentiment with irrelevant data
- [ ] Content deduplication (URL hash + content hash) — extend existing deduplication_service.py
- [ ] Tier 1 RoBERTa classifier — replaces AskNews pre-computed sentiment
- [ ] REST API backward compatibility — don't break the existing frontend

### Add After Core Works (v2.1)

- [ ] Dev.to collector — low complexity, adds blog-style signal; trigger: core pipeline stable and running for 1 week
- [ ] Discourse collector (forum.cursor.com) — medium complexity; trigger: basic polling pattern proven with HN/Reddit
- [ ] Embedding relevance filter (all-MiniLM-L6-v2) — improves signal quality; trigger: false positive rate observed to be a problem in core pipeline
- [ ] Tier 2 LLM extraction (GPT-4o-mini) — aspect-level sentiment; trigger: Tier 1 running in production for 1 week
- [ ] Per-source sentiment breakdown in API — trigger: multiple sources shipping data

### Future Consideration (v2.2+)

- [ ] GitHub Issues + Discussions collector — high implementation cost (GraphQL for Discussions); defer
- [ ] MinHash near-dedup (datasketch) — defer until exact dedup proves insufficient in practice
- [ ] Frontend aspect-level sentiment charts — defer until Tier 2 data exists (weeks of accumulation needed)
- [ ] Sentiment spike alerting — defer until baseline sentiment is established from real data
- [ ] Fine-tuned RoBERTa on developer text — defer until labeled examples accumulate from Tier 2 outputs

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Common Post Schema | HIGH | LOW | P1 |
| Storage schema migration | HIGH | HIGH | P1 |
| HN Algolia collector | HIGH | LOW | P1 |
| Reddit PRAW collector | HIGH | MEDIUM | P1 |
| Keyword relevance filter | HIGH | LOW | P1 |
| Content deduplication (hash) | HIGH | LOW | P1 |
| Tier 1 RoBERTa classifier | HIGH | MEDIUM | P1 |
| REST API backward compat | HIGH | LOW | P1 |
| Dev.to collector | MEDIUM | LOW | P2 |
| Discourse collector | MEDIUM | MEDIUM | P2 |
| Embedding relevance filter | MEDIUM | MEDIUM | P2 |
| Tier 2 LLM extraction | HIGH | HIGH | P2 |
| Aspect-level sentiment (schema only) | HIGH | MEDIUM | P2 |
| Per-source API breakdown | MEDIUM | LOW | P2 |
| GitHub Issues collector | MEDIUM | HIGH | P3 |
| GitHub Discussions collector | MEDIUM | HIGH | P3 |
| MinHash near-dedup | LOW | MEDIUM | P3 |
| Frontend aspect-level charts | HIGH | HIGH | P3 |
| Sentiment spike alerts | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v2.0 launch (replaces AskNews)
- P2: Should have, add in v2.1 after core is stable
- P3: Nice to have, v2.2+ future consideration

---

## Expected Behavior Per Feature

### HN Algolia Collector
- Query: `https://hn.algolia.com/api/v1/search_by_date?query={tool_name}&tags=comment&numericFilters=points>2`
- Pagination: `page=0,1,2...` but capped at 1,000 total hits per query; use `created_at_i` timestamp range filtering to work around cap for historical backfill
- Poll interval: every 15-30 minutes via existing APScheduler pattern
- Expected output per run: 50-500 comments across all tool name queries

### Reddit PRAW Collector
- Subreddits: r/LocalLLaMA, r/cursor, r/copilot, r/ChatGPT, r/vscode, r/programming (at minimum)
- Fetch: `subreddit.new(limit=100)` + `subreddit.hot(limit=25)` per subreddit per run
- PRAW handles OAuth refresh and rate limiting automatically; use script-type app credentials
- Poll interval: every 15 minutes; PRAW's built-in rate limit sleeping keeps within 100 QPM
- Expected output per run: 100-500 posts across subreddits; 1,000-post per-listing ceiling rarely matters at this polling frequency

### Discourse Collector
- Target: `forum.cursor.com` (and optionally `community.openai.com` in v2.1)
- Endpoints: `GET /latest.json?page=N`, `GET /t/{topic_id}.json` for post content
- No auth required for public posts on most Discourse instances
- Rate limit approach: 1 request/second as conservative default; exponential backoff on 429s
- Poll interval: every 60 minutes (lower post volume than Reddit/HN)

### Dev.to Collector
- Use v1 API (v0 is deprecated per Forem docs)
- Endpoint: `GET https://dev.to/api/articles?tag=ai&per_page=30&page=1`
- Tags to query: `ai`, `cursor`, `copilot`, `llm`, `github-copilot`
- No auth required for reads; API key optional for higher limits if rate limited
- Poll interval: every 60 minutes

### GitHub Issues Collector (MVP scope)
- REST endpoint: `GET /repos/{owner}/{repo}/issues?state=open&sort=updated&direction=desc`
- Key repos: `getcursor/cursor`, `continuedev/continue`, `TabbyML/tabby`, `microsoft/vscode-copilot-release`, `sourcegraph/cody`
- Auth: personal access token (5,000 REST req/hr authenticated)
- Poll interval: every 60 minutes

### Keyword Relevance Filter
- Tool name list: Copilot, Cursor, Windsurf, Cody, Tabnine, CodeWhisperer, Amazon Q, Continue, Aider, Claude Code, Devin, Supermaven, Replit AI
- Contextual terms: "AI coding", "code completion", "AI pair programming", "LLM coding", "autocomplete", "AI assistant"
- Negative keywords: "airline copilot", "database cursor", "film cursor" for common false positives
- Implementation: pure Python string matching (case-insensitive); runs in microseconds per post

### Tier 1 RoBERTa Classifier
- Model: `cardiffnlp/twitter-roberta-base-sentiment-latest` from Hugging Face
- Load once at app startup via `transformers` pipeline; keep in memory
- Output per post: `{label: "positive|neutral|negative", score: float}`
- Routing rule: route to Tier 2 if label is not neutral OR if confidence (score) is below 0.85; otherwise store as neutral
- Expected throughput: 10-20 posts/sec on CPU; sufficient for 10,000 posts/day in batch
- Known limitation: sarcasm and technical comparisons ("context window is 128K vs 200K") may score incorrectly

### Tier 2 LLM Extraction
- Model: GPT-4o-mini via OpenAI API
- Receives: post text + Tier 1 label + confidence score as context
- Output schema (Pydantic):
  ```python
  class AspectSentiment(BaseModel):
      performance: Optional[float] = None      # -1.0 to 1.0
      cost_pricing: Optional[float] = None
      code_quality: Optional[float] = None
      reliability: Optional[float] = None
      ux_developer_experience: Optional[float] = None
      speed_latency: Optional[float] = None
      context_window: Optional[float] = None

  class ToolSentiment(BaseModel):
      tool_name: str
      overall_sentiment: float
      aspects: AspectSentiment
      evidence_quote: str       # 200-300 char excerpt
      is_comparative: bool
      sarcasm_detected: bool
  ```
- Use OpenAI SDK `.beta.chat.completions.parse()` with Pydantic model for guaranteed valid JSON (100% reliability per OpenAI structured outputs)
- Estimated cost: $20-30/month at 5,000 posts/day with 40% routing rate

### Content Deduplication
- Primary: SHA-256 hash of normalized URL (already in `deduplication_service.py` pattern)
- Secondary: SHA-256 hash of content body (catches reposts with different URLs or shortened links)
- Extend existing `batch_check_duplicates` function to new `posts` table
- Near-dedup (MinHash via `datasketch`) deferred to v2.2

---

## Existing Architecture Impact (v1.0 Preservation)

These v1.0 features are already built and must be preserved or extended — not replaced:

| Existing v1.0 Feature | v2.0 Impact |
|----------------------|-------------|
| `deduplication_service.py` (SHA-256 URL hash) | Extend to new `posts` table; keep existing function signatures where possible |
| `sentiment_service.py` (store_sentiment_timeseries) | Keep for backward compat; add new storage functions for posts/tool_mentions/sentiment_scores |
| APScheduler in `scheduler.py` | Add new collector jobs; keep existing interval pattern and job structure |
| Entity normalization (50+ name variations for 10 AI tools) | Reuse directly; keyword filter uses same tool name list |
| REST API entity endpoints + cursor pagination | Preserve contract; add new endpoints for per-source breakdown alongside existing ones |
| PostgreSQL + Alembic migrations | Add new tables via migrations; do not alter existing `SentimentTimeseries` table structure |
| Docker Compose with health checks | Add env vars for `OPENAI_API_KEY`, model cache paths; no structural changes to Compose file |

---

## Competitor Feature Analysis

| Feature | Brandwatch / Sprout | Obsei (open source, 1,400 stars) | VibeCheck v2.0 |
|---------|---------------------|----------------------------------|----------------|
| Source coverage | Twitter, FB, Instagram (paid APIs) | Reddit, Twitter observers | HN, Reddit, Discourse, GitHub, Dev.to (all free) |
| Sentiment model | Proprietary general NLP | VADER, basic transformers | Two-tier: RoBERTa + GPT-4o-mini structured extraction |
| Aspect-level sentiment | Enterprise tier only, domain-agnostic | Not built-in | Built-in via Tier 2; developer-specific aspects |
| Developer text focus | None (general social listening) | None | Purpose-built for developer community discourse |
| Cost | $800-5,000/month | Free (infra cost only) | $0-50/month target |
| AI coding tool focus | None | None | Purpose-built; no direct competitor at this price point |

---

## Sources

- [HN Algolia Search API docs](https://hn.algolia.com/api) — official; no auth required; 1,000 hit pagination limit confirmed via GitHub issue #230 on algolia/hn-search
- [Reddit API Rate Limits 2026 Guide](https://painonsocial.com/blog/reddit-api-rate-limits-guide) — 100 QPM confirmed for free non-commercial OAuth tier
- [PRAW Rate Limits documentation](https://praw.readthedocs.io/en/stable/getting_started/ratelimits.html) — PRAW handles OAuth + rate limiting automatically; official PRAW docs
- [Discourse API rate limits meta](https://meta.discourse.org/t/api-rate-limits/208405) — rate limits are instance-configured in app.yml; no published default numeric limit
- [Forem API v1 docs](https://developers.forem.com/api/v1) — Dev.to v0 deprecated; use v1
- [GitHub GraphQL rate limits](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api) — 5,000 points/hr (NOT requests); point cost varies by query complexity
- [cardiffnlp/twitter-roberta-base-sentiment-latest](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest) — trained on 124M tweets; TweetEval benchmark; sarcasm limitation documented
- [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — 384-dim; 14,200 sentences/sec; 256 word piece max input length
- [GPT-4o-mini model page](https://developers.openai.com/api/docs/models/gpt-4o-mini) — $0.15/M input, $0.60/M output; Pydantic structured output via SDK `.parse()`
- [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/) — 100% reliable JSON on gpt-4o-mini via constrained decoding
- `sentiment_analysis_improvement.md` — project-internal architecture report; HIGH confidence for cost estimates and pipeline design rationale

---
*Feature research for: VibeCheck v2.0 — free data source ingestion + two-tier sentiment pipeline*
*Researched: 2026-02-19*
