# VibeCheck

## What This Is

A backend data pipeline and REST API that tracks public sentiment around popular AI models and tools over time. Uses the AskNews API (News Search + Story Clustering) to ingest news articles and Reddit threads on a schedule, processes sentiment data with entity normalization, and serves time-series results via FastAPI. A React frontend consumes the API with real-time trend calculations and sparkline visualizations.

## Core Value

Users can see how sentiment around AI models and tools has changed over time, with clear time-series data powered by real news and Reddit community opinion.

## Requirements

### Validated

- ✓ Vite + React + TypeScript frontend scaffold — existing
- ✓ shadcn/ui component library — existing
- ✓ Vitest testing setup — existing
- ✓ AskNews API integration with Python SDK (OAuth2 auth) — v1.0
- ✓ Hybrid data ingestion: `/news` with entity filters + `/stories` for narrative clustering — v1.0
- ✓ Fixed curated entity list (5 AI models + 5 AI tools) — v1.0
- ✓ Scheduled polling jobs (news every 15 min, stories every 60 min) — v1.0
- ✓ PostgreSQL storage for articles, sentiment time-series, and Reddit threads — v1.0
- ✓ Sentiment aggregation: daily/hourly averages per entity, separate news vs Reddit — v1.0
- ✓ FastAPI backend serving REST endpoints for the frontend — v1.0
- ✓ Entity sentiment history endpoint with cursor-based pagination — v1.0
- ✓ Docker Compose environment with health checks and auto-migrations — v1.0
- ✓ Environment-aware CORS middleware for frontend integration — v1.0
- ✓ Automated entity seeding on startup — v1.0

### Active

- [ ] Replace AskNews with 5 free data sources (HN, Reddit, Discourse, GitHub, Dev.to)
- [ ] Two-tier sentiment pipeline: self-hosted RoBERTa + hosted LLM (OpenAI-compatible API)
- [ ] Relevance filtering: keyword matching + embedding similarity + deduplication
- [ ] New schema: posts, sentiment_scores, tool_mentions with aspect-level data
- [ ] Frontend: aspect-level sentiment views, source breakdowns, tool comparisons

### Out of Scope

- Real-time WebSocket updates — REST sufficient for current needs
- Alert/notification system — defer to v3
- Sentiment forecasting/ML — defer to v3+
- Twitter/X API — too expensive ($200/mo), developer discourse has migrated elsewhere
- YouTube comments — lower priority, defer to v2.1
- Own NLP fine-tuning — use pre-trained models, fine-tune only if quality gaps emerge
- Grafana dashboards — keep React frontend, better UX for target users

## Current Milestone: v2.0 Free Pipeline

**Goal:** Replace the $250/mo AskNews API with free data sources and a self-hosted/cheap sentiment pipeline, while evolving the frontend to display richer aspect-level sentiment data.

**Target features:**
- 5 free data sources: Hacker News, Reddit, Discourse forums, GitHub Issues/Discussions, Dev.to
- Two-tier sentiment: RoBERTa classifier ($0) + hosted OSS LLM (~$2-5/mo) via OpenAI-compatible API
- Relevance filtering with keyword matching, embedding similarity, and deduplication
- Aspect-level sentiment (performance, cost, reliability, UX, speed, code quality, context window)
- Frontend: source breakdowns, aspect charts, tool-vs-tool comparisons

## Context

**Shipped v1.0** with 3,347 LOC Python (backend) + 6,403 LOC TypeScript (frontend).

**Tech stack:**
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 async, asyncpg, APScheduler
- Frontend: Vite, React, TypeScript, shadcn/ui, Tailwind, React Query
- Infrastructure: Docker Compose, PostgreSQL 16, Alembic migrations
- Deployment: Render (backend web service + PostgreSQL)

**v2.0 additions planned:**
- PRAW (Reddit), httpx (HN Algolia, Discourse, Dev.to, GitHub GraphQL)
- transformers + twitter-roberta-base-sentiment-latest (Tier 1 classifier)
- sentence-transformers/all-MiniLM-L6-v2 (embedding-based filtering)
- OpenAI-compatible LLM client for Tier 2 extraction (Groq/DeepInfra/Gemini)
- datasketch (MinHash deduplication)

**Known tech debt:**
- Unique constraint on `sentiment_timeseries(entity_id, timestamp, period)` not yet added
- Entity variation dictionary may need tuning with more real API data
- AskNews SDK and `httpx` pin to be removed in v2.0

## Constraints

- **Tech stack (backend)**: Python with FastAPI
- **Tech stack (frontend)**: Vite + React + TypeScript
- **Database**: PostgreSQL
- **API budget**: AskNews Spelunker tier ($250/mo, ~4,000-5,000 requests/month)
- **Model profile**: Budget — cost-efficient models for GSD agents

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid AskNews approach (News Search + Story Clustering) | News search gives high-precision entity tracking; story clustering adds Reddit sentiment | ✓ Good — both endpoints working, Reddit data extracted |
| Use AskNews built-in sentiment (no own NLP) | AskNews provides article-level and story-level sentiment including Reddit | ✓ Good — sentiment scores mapped to 0.5/-0.5/0.0 scale |
| Fixed curated entity list (10 entities) | Simpler implementation, controlled API costs, consistent tracking | ✓ Good — entity normalization handles 50+ variations |
| PostgreSQL for storage | Reliable for time-series, good query support, production-ready | ✓ Good — composite indexes optimize time-series queries |
| FastAPI for backend | Python ecosystem, async support, auto OpenAPI docs | ✓ Good — async throughout with SQLAlchemy 2.0 |
| Scheduled polling (not on-demand) | Consistent collection, predictable costs, no cold-start | ✓ Good — APScheduler with 15min/60min intervals |
| Cursor-based pagination for time-series | Avoids offset drift/duplicates in time-series data | ✓ Good — ISO timestamp cursors work well |
| Entity seeding as fatal startup dependency | Empty entity table breaks foreign keys and all ingestion | ✓ Good — prevents silent failure mode |
| Reddit sentiment as separate field | Enables media vs community divergence analysis | ✓ Good — `reddit_sentiment` + `reddit_thread_count` tracked |
| Docker WORKDIR = `/app` (backend/) | Container imports use relative paths, no `backend.` prefix | ⚠️ Revisit — caused initial import confusion |

---
*Last updated: 2026-02-19 after v2.0 milestone start*
