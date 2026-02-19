# Project Research Summary

**Project:** VibeCheck v2.0
**Domain:** Brownfield FastAPI + PostgreSQL — multi-source developer sentiment tracking with ML pipeline
**Researched:** 2026-02-19
**Confidence:** HIGH (stack and pitfalls HIGH, architecture MEDIUM-HIGH, features HIGH)

## Executive Summary

VibeCheck v2.0 is a brownfield migration: the v1.0 AskNews-based sentiment pipeline is replaced with five free data sources (HN Algolia, Reddit, Discourse, Dev.to, GitHub Issues) and an own two-tier sentiment pipeline (RoBERTa for bulk classification, GPT-4o-mini for aspect-level extraction). The recommended approach follows a strict dependency chain — schema migration first, then data collection clients, then sentiment pipeline, then API evolution — because the existing frontend and database must remain functional throughout. The v1.0 infrastructure (APScheduler, PostgreSQL, FastAPI, asyncpg, Alembic) stays unchanged; only the clients, jobs, and services layer changes.

The defining technical constraint is Render's memory ceiling. Loading `cardiffnlp/twitter-roberta-base-sentiment-latest` (~500MB disk, 700-900MB in RAM) requires upgrading to Render Standard ($25/month, 2GB RAM) before any ML work ships. This is non-negotiable and must be resolved at the start of the ML pipeline phase. Loading both RoBERTa and DeBERTa ABSA models simultaneously is infeasible on Standard tier, so aspect-level extraction relies on Tier 2 LLM (Groq/GPT-4o-mini) rather than a second local model.

The key risks are: (1) OOM kills from ML models on under-specced Render tiers; (2) Alembic autogenerate dropping existing tables on the brownfield schema if `env.py` imports are wrong; (3) Reddit OAuth app type misconfiguration blocking all data collection; (4) frontend breakage if API response shapes change before the frontend is updated. All four are preventable with explicit validation steps before each phase ships.

---

## Key Findings

### Recommended Stack

The v1.0 stack (Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0+, asyncpg, Alembic, APScheduler, PostgreSQL 16) remains unchanged and is well-suited for v2.0. New additions are: `asyncpraw==7.8.1` for async Reddit access (do not use sync `praw` — it blocks the event loop), `transformers==4.57.3` + CPU-only PyTorch for RoBERTa inference, `sentence-transformers==5.2.3` for optional embedding-based relevance filtering, `datasketch==1.9.0` for future near-dedup, and `openai>=2.21.0` as the client for both Groq (primary LLM, free tier) and GPT-4o-mini. Torch must be installed with the CPU-only index URL in Dockerfile (`--index-url https://download.pytorch.org/whl/cpu`) or the CUDA variant balloons the Docker image to 4-6GB.

**Core technologies:**
- asyncpraw 7.8.1: Reddit async data collection — only async-native PRAW; maintains FastAPI event loop compatibility
- transformers 4.57.3 + CPU torch: Tier 1 RoBERTa sentiment — avoid v5.x (RC only as of Feb 2026); CPU-only required for Render
- sentence-transformers 5.2.3: Embedding relevance filter (v2.1, optional) — 22MB model, 14,200 sentences/sec
- openai>=2.21.0: Tier 2 LLM client — base_url swap covers Groq/DeepInfra/OpenAI with zero code change
- httpx 0.28.1: Upgraded from 0.25.2 (removes asknews constraint); covers HN, Discourse, GitHub, Dev.to clients

**Critical deployment requirement:** Render Standard tier (2GB RAM, $25/month) is required before loading any ML model. Free and Starter tiers (512MB) OOM before RoBERTa finishes loading.

### Expected Features

**Must have — v2.0 core (replaces AskNews at $0-50/month):**
- Common Post Schema — normalized schema across all 5 sources; every downstream component depends on it
- Storage schema migration (posts + post_entity_mentions + aspect_sentiments tables) — prerequisite for all collectors
- HN Algolia collector — highest-signal free source, no auth, simplest client to implement
- Reddit PRAW collector — second-highest signal; asyncpraw handles OAuth and rate limiting
- Keyword relevance filter — prevents irrelevant posts from corrupting sentiment signal
- Content deduplication (URL + body hash) — extends existing deduplication_service.py
- Tier 1 RoBERTa classifier — replaces AskNews pre-computed sentiment scores
- REST API backward compatibility — existing frontend endpoints must not break during migration

**Should have — v2.1 (after core is stable for 1 week):**
- Dev.to collector — low complexity, adds blog-style opinion signal
- Discourse collector (forum.cursor.com) — medium complexity, high signal-to-noise forum data
- Tier 2 LLM extraction (GPT-4o-mini) — aspect-level sentiment with sarcasm detection; depends on Tier 1 routing
- Embedding relevance filter (all-MiniLM-L6-v2) — add only if keyword filter shows high false-positive rate in production
- Per-source sentiment breakdown in API

**Defer to v2.2+:**
- GitHub Issues collector — higher implementation cost; GitHub Discussions requires GraphQL (entirely different client pattern)
- MinHash near-deduplication (datasketch) — defer until exact URL hash proves insufficient in practice
- Frontend aspect-level charts — defer until weeks of Tier 2 data accumulate
- Fine-tuned RoBERTa on developer text — defer until labeled examples accumulate from Tier 2 outputs

**Anti-features (do not build):**
- Twitter/X integration — free tier is ~500 reads/month; unusable for any polling use case
- Celery/Redis — APScheduler is sufficient; Celery requires message broker and adds operational overhead for no gain at this scale
- Separate vector database (Pinecone, Weaviate) — pgvector on existing PostgreSQL is sufficient at 1,000-10,000 posts/day
- Raw post text stored permanently — GDPR exposure and Reddit ToS require deletion compliance; store evidence_quote excerpts (200-300 chars) instead

### Architecture Approach

The v2.0 architecture adds new components alongside existing ones without replacing the core infrastructure. The pattern is: APScheduler fires a unified `collection_job.py` (replacing `news_job.py` + `stories_job.py`) that runs all 5 source clients concurrently via `asyncio.gather(..., return_exceptions=True)` so one failing source does not abort all others. A separate `sentiment_job.py` processes new posts in batch — keyword filter first, RoBERTa second, Tier 2 LLM for ambiguous cases. An `aggregation_job.py` recomputes `sentiment_timeseries` rollups from the new `posts` + `post_entity_mentions` tables. All three run on distinct schedules (collection every 30 min / sentiment every 60 min / aggregation every 60 min offset by 15 min).

**Major components:**
1. `pipeline/clients/` — 5 new source clients (hn_client, reddit_client, discourse_client, github_client, devto_client); all expose the same `fetch_recent(entity_names, since_hours) -> list[PostDict]` interface
2. `pipeline/jobs/` — 3 new jobs (collection, sentiment, aggregation); 2 old jobs removed (news_job, stories_job)
3. `pipeline/services/` — 4 new services (relevance_filter, roberta_service, llm_service, aspect_service); 2 kept unchanged (dedup_service, entity_service); 1 replaced (sentiment_service was AskNews-specific)
4. `db/models.py` — 3 new tables (posts, post_entity_mentions, aspect_sentiments) + 1 modified (sentiment_timeseries adds source_breakdown JSONB column)
5. `api/routes/` — 1 modified (entities.py adds source_breakdown and aspect endpoints) + 1 new (posts.py raw feed)

**Schema migration strategy:** Additive-only (Option A: parallel tables). Create `posts` table alongside existing `articles`; new collectors write to `posts`; API routes shift gradually; drop `articles` in a later milestone after verifying coverage. Never alter existing `SentimentTimeseries` structure destructively.

**ML model loading pattern:** Load RoBERTa lazily inside `sentiment_job.py` — only when the batch job runs. Do NOT load at FastAPI startup (wastes 700-900MB RAM for the entire API uptime). Run all transformer inference via `loop.run_in_executor(None, ...)` to avoid blocking the async event loop.

### Critical Pitfalls

1. **RoBERTa OOM kills the Render dyno** — Upgrade to Standard tier ($25/mo, 2GB RAM) before loading any transformer model. Alternative: use DistilRoBERTa + ONNX quantization (~150-200MB). OOM kills surface as silent service restarts with no Python traceback — easy to misdiagnose.

2. **Alembic drops existing tables on brownfield autogenerate** — Always inspect autogenerated migration files for `drop_table()` calls before applying. Verify `env.py` uses Docker import paths (no `backend.` prefix; WORKDIR is `/app`). Take `pg_dump` backup before every schema migration. This is a data-destruction risk, not just a delay.

3. **Reddit OAuth app type misconfiguration** — Register a "script" type app (not web app). Use `asyncpraw` not `praw`. Set redirect URI to `http://localhost:8080` (required but never called). User-Agent must follow `platform:app_id:version (by /u/username)` format or requests are aggressively rate-limited and access tokens do not refresh.

4. **Frontend breakage during API evolution** — Treat existing API contract as frozen during migration. Add new endpoints rather than modifying existing ones. Use Expand-Contract pattern: add new fields alongside old ones, update frontend, then remove old fields. The existing `entityTransformer.ts` and `trendCalculator.ts` are tightly coupled to current field names.

5. **sentence-transformers memory growth over time** — Process embeddings in chunks of max 32 posts; call `torch.cuda.empty_cache()` after each chunk (works on CPU, triggers GC). Run embedding computation in background job, not in FastAPI web process. Validate RSS memory is stable over 24 hours before marking embedding phase complete.

---

## Implications for Roadmap

Based on research, the dependency chain is strict: schema must precede all collectors; collectors must precede the sentiment pipeline; Tier 1 must precede Tier 2. The suggested 6-phase structure maps directly to these dependencies.

### Phase 1: Schema Migration and Infrastructure
**Rationale:** All new components write to new tables. Nothing else can proceed without the schema. This phase carries the highest risk of data destruction (Pitfall 2 — Alembic drops tables) and must be validated on staging before any other work begins. Render Standard tier must be provisioned here before ML work starts in Phase 3.
**Delivers:** posts, post_entity_mentions, aspect_sentiments tables; source_breakdown JSONB on sentiment_timeseries; updated SQLAlchemy models; Render Standard tier confirmed working
**Addresses:** Storage schema migration (table stakes), REST API backward compatibility (additive-only constraint)
**Avoids:** Alembic brownfield migration data loss (inspect every autogenerated migration; pg_dump backup before applying)

### Phase 2: Data Collection Clients
**Rationale:** Raw data must exist before the sentiment pipeline can process it. All 5 clients are independent of each other and can be developed in parallel within the phase. The keyword relevance filter should be wired in at collection time to avoid storing irrelevant posts.
**Delivers:** Working HN, Reddit, Dev.to, Discourse, and GitHub Issues clients; collection_job.py orchestration; keyword relevance filter; APScheduler updated (old jobs removed, new collection job registered); posts appearing in DB from all sources
**Uses:** asyncpraw==7.8.1 (Reddit), httpx==0.28.1 (HN, Dev.to, Discourse, GitHub)
**Avoids:** Reddit OAuth misconfiguration (validate auth in isolation before pipeline integration); HN pagination silent failures (cap at page 10, narrow time windows instead of paginating deep); Reddit burst rate limiting (semaphore, 0.6s inter-request delay); Dev.to unauthenticated rate limits (use API key even though reads are free)

### Phase 3: Tier 1 Sentiment Pipeline (RoBERTa)
**Rationale:** Core of the new pipeline. This is the most technically risky phase — Render memory must be validated before building more. Do not proceed to Tier 2 or aggregation until RoBERTa is confirmed stable on the actual Render instance under sustained load.
**Delivers:** roberta_service.py (batch inference via run_in_executor, lazy load); sentiment_job.py (fetches unscored posts, runs Tier 1); posts.roberta_score populated; memory profile validated over 24-hour window on Render Standard
**Uses:** transformers==4.57.3, CPU-only torch (Dockerfile RUN pip install torch --index-url https://download.pytorch.org/whl/cpu), cardiffnlp/twitter-roberta-base-sentiment-latest
**Avoids:** RoBERTa OOM (Render Standard required; lazy load in job not at API startup; use `torch.no_grad()` during inference); synchronous ML inference blocking async event loop (always use run_in_executor)

### Phase 4: Aggregation and API Evolution
**Rationale:** Only meaningful once sentiment scores exist in posts. The aggregation_job.py computes sentiment_timeseries rollups from the new posts + post_entity_mentions tables, enabling the frontend to consume per-source data without breaking existing endpoints. The Expand-Contract pattern ensures zero frontend breakage.
**Delivers:** aggregation_job.py; source_breakdown JSONB populated in sentiment_timeseries; entities.py route extended with source_breakdown field; new posts.py raw feed route; all 3 new APScheduler jobs registered
**Addresses:** Per-source sentiment breakdown (v2.0 differentiator), REST API backward compatibility
**Avoids:** Frontend breakage during API evolution (add new fields alongside old ones; validate existing endpoint contract before every deploy; the `entityTransformer.ts` must not receive unexpected null values)

### Phase 5: Tier 2 LLM and Aspect Extraction
**Rationale:** Enhancement layer; app fully replaces AskNews after Phase 4. Tier 2 requires Tier 1 in production for 1+ week to establish routing baseline and cost projections. Aspect-level schema is already created in Phase 1, so this phase only adds the extraction logic.
**Delivers:** llm_service.py (Groq primary via openai base_url override, GPT-4o-mini fallback); aspect_service.py; aspect_sentiments populated; GET /api/entities/{id}/aspects endpoint
**Uses:** openai>=2.21.0; Pydantic structured output via .beta.chat.completions.parse() for 100% valid JSON; tenacity retry with exponential backoff on 429/503
**Avoids:** LLM silent extraction failures (always validate against Pydantic schema; never store raw LLM text); LLM API budget overrun (validate per-day call count against tier limits before enabling; route only ~30-40% of posts to Tier 2); serial LLM calls creating latency (asyncio.gather + Semaphore(5) for controlled concurrency)

### Phase 6: Frontend Evolution
**Rationale:** Backend data must accumulate before the frontend can display it meaningfully. Aspect charts require weeks of Tier 2 data. Source breakdown can ship as soon as Phase 4 data exists.
**Delivers:** Source breakdown selector (HN/Reddit/etc. toggle); aspect sentiment tab component; updated mention feed using post_entity_mentions JOIN (replaces slow ILIKE queries on title)
**Addresses:** Per-source sentiment breakdown (frontend), aspect-level sentiment charts
**Avoids:** TypeScript silent failures from API contract changes (add runtime type guards in api.ts that surface violations as visible errors rather than undefined access)

### Phase Ordering Rationale

- Schema is gate zero: every subsequent phase writes to the new tables; doing schema last is the most common brownfield mistake and causes rework
- Clients before pipeline: you cannot tune or validate a sentiment pipeline without real data flowing through it
- Tier 1 before Tier 2: Tier 2 routing decisions are based on Tier 1 confidence scores; building Tier 2 first is architecturally impossible
- Memory validation before further ML work: Render memory is a hard ceiling; discovering OOM in Phase 5 means rearchitecting Tier 1 retroactively
- Aggregation before frontend: the frontend consumes aggregated timeseries; without the aggregation job running there is no data to display

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Tier 1 ML Pipeline):** Memory profiling on Render Standard is empirical — exact behavior of cardiffnlp model under sustained batch load needs validation with actual inference workload, not just model loading. Run a memory spike test before committing to full implementation.
- **Phase 5 (Tier 2 LLM):** Cost modeling depends on observed Tier 1 routing rate (what percentage of posts actually reach Tier 2). This cannot be known until Phase 3 has run in production for 1+ week. Budget $20-30/month as planning estimate; validate before enabling at scale.

Phases with standard patterns (can skip deeper research):
- **Phase 1 (Schema Migration):** Alembic additive migrations are well-documented; follow inspection checklist and backup protocol; no novel patterns needed.
- **Phase 2 (Data Clients):** HN Algolia, Dev.to, and GitHub APIs have stable official documentation. Reddit is well-covered by asyncpraw docs. Specific pitfalls are known and documented.
- **Phase 4 (Aggregation + API):** Standard SQLAlchemy upsert pattern; Expand-Contract API evolution is a documented pattern.
- **Phase 6 (Frontend):** React/TypeScript component work with known API shapes; no novel integration patterns required.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified via official sources Feb 2026; version constraints explicit and tested against compatibility matrix |
| Features | HIGH | Clear P1/P2/P3 prioritization; dependency chain validated; anti-features well-reasoned against cost and ToS constraints |
| Architecture | MEDIUM-HIGH | Component boundaries clear and mapped to existing v1.0 structure; Render memory math verified; DeBERTa ABSA co-loading risk is MEDIUM |
| Pitfalls | HIGH | All 5 critical pitfalls verified against official docs and Render community reports; mitigation code examples provided |

**Overall confidence:** HIGH

### Gaps to Address

- **DeBERTa ABSA feasibility on Render Standard:** Loading RoBERTa + DeBERTa simultaneously is ~1.8GB combined — too close to 2GB ceiling. Architecture recommends LLM Tier 2 for aspect extraction instead of a second local model. Validate this decision holds before Phase 5 planning if aspect-level accuracy becomes a requirement.
- **Discourse rate limits per instance:** Rate limits are instance-configured and not published. Use 1 req/sec conservative default; may need tuning per forum. Validate against forum.cursor.com specifically before claiming Discourse collector is complete in Phase 2.
- **Aggregation job correctness:** Sentiment rollup logic from the new posts table must produce results consistent with what v1.0 `sentiment_timeseries` contained. A discrepancy in methodology could break frontend trend display. Add an explicit verification step at the end of Phase 4.
- **Render Standard cold start with ML models:** Model download time (~600MB from HuggingFace Hub) on first deploy is 30-60 seconds. A readiness check before APScheduler fires the first sentiment_job is needed to avoid job failure on cold start. Consider pre-baking models into the Docker image in Phase 3 planning.

---

## Sources

### Primary (HIGH confidence)
- FastAPI 0.115+ official docs — async lifespan events, background tasks
- asyncpraw 7.8.1 official docs (asyncpraw.readthedocs.io) — OAuth app types, rate limit headers, async patterns
- HN Algolia API official docs (hn.algolia.com/api) — pagination limits (1,000 hits), search_by_date filter syntax
- cardiffnlp/twitter-roberta-base-sentiment-latest on HuggingFace — model size, TweetEval accuracy benchmarks, known sarcasm limitation
- sentence-transformers 5.2.3 on HuggingFace — model size, inference speed, 256 token max input length
- openai>=2.21.0 PyPI (released Feb 14 2026) — structured output API via .parse(), base_url override for Groq/DeepInfra
- SQLAlchemy 2.0 / Alembic official docs — autogenerate behavior, brownfield migration patterns, named constraints
- Render community forums — memory limits per tier (512MB free/starter, 2GB Standard at $25/mo)
- PyTorch CPU-only install GitHub issue #146786 — `--index-url https://download.pytorch.org/whl/cpu` requirement

### Secondary (MEDIUM confidence)
- Render community OOM error reports — confirmed RoBERTa OOM on starter tier via community reports
- Milvus sentence-transformers memory footprint guide — batching strategy (max 32 items, explicit cleanup between chunks)
- LLM retry patterns (2025 community practice) — tenacity + exponential backoff with jitter for 429/503
- project-internal sentiment_analysis_improvement.md — cost estimates ($20-30/month at 5K posts/day) and pipeline design rationale

### Tertiary (LOW confidence)
- Discourse API rate limits (meta.discourse.org) — rates vary by instance; 1 req/sec is conservative estimate, not verified for forum.cursor.com specifically

---
*Research completed: 2026-02-19*
*Ready for roadmap: yes*
