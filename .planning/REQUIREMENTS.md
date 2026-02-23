# Requirements: VibeCheck

**Defined:** 2026-02-19
**Core Value:** Users can see how sentiment around AI models and tools has changed over time, with clear time-series data powered by real developer community opinion across multiple free platforms.

## v2.0 Requirements

Requirements for v2.0 Free Pipeline milestone. Each maps to roadmap phases.

### Infrastructure

- [x] **INFRA-01**: System migrates to new schema (posts, tool_mentions, aspect_sentiments) via Alembic without breaking existing data
- [x] **INFRA-02**: AskNews SDK removed and httpx upgraded to 0.28.1
- [x] **INFRA-03**: Render deployment upgraded to Standard tier ($25/mo) for ML model support

### Data Collection

- [x] **COLL-01**: System collects developer posts from Hacker News via Algolia API on a schedule
- [x] **COLL-02**: System collects developer posts from Reddit subreddits via asyncpraw on a schedule
- [x] **COLL-03**: System collects developer posts from Discourse forums (Cursor, OpenAI) on a schedule
- [x] **COLL-04**: System collects developer articles from Dev.to via Forem API v1 on a schedule
- [x] **COLL-05**: Keyword relevance filter rejects irrelevant posts before storage using tool names and context terms
- [x] **COLL-06**: Content deduplication prevents duplicate posts across all sources via hash-based detection

### Sentiment Analysis

- [x] **SENT-01**: Tier 1 RoBERTa classifier scores every post as positive/negative/neutral with confidence
- [x] **SENT-02**: Tier 2 LLM extracts structured aspect-level sentiment for non-neutral/low-confidence posts
- [x] **SENT-03**: LLM backend is configurable via env vars (Groq, DeepInfra, or GPT-4o-mini)
- [x] **SENT-04**: Aspect-level sentiment stored per tool mention (performance, cost, reliability, UX, speed, code quality, context window)

### Frontend

- [x] **FRON-01**: User can see sentiment breakdown by data source (HN, Reddit, Discourse, Dev.to)
- [x] **FRON-02**: User can see aspect-level sentiment charts per entity

## Future Requirements

Deferred to v2.1 or later. Tracked but not in current roadmap.

### Data Collection

- **COLL-07**: System collects developer posts from GitHub Issues via REST API
- **COLL-08**: System collects developer posts from GitHub Discussions via GraphQL API
- **COLL-09**: Embedding-based similarity filter catches semantically relevant posts that keywords miss
- **COLL-10**: MinHash near-duplicate detection catches cross-platform reposts

### Frontend

- **FRON-03**: User can compare two tools side-by-side on a comparison page
- **FRON-04**: User can see a feed of recent posts driving sentiment scores
- **FRON-05**: Sentiment spike alerts notify user of sudden changes

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Twitter/X integration | Free tier caps at ~500 reads/month; Basic costs $200/mo. Developer discourse has migrated elsewhere. |
| YouTube comments | Lower priority, defer to v2.1+ |
| Own NLP fine-tuning | Use pre-trained models; fine-tune only if quality gaps emerge in production |
| Grafana dashboards | Keep React frontend — better UX for target users per UI/UX evaluation |
| Real-time WebSocket updates | REST polling sufficient for current needs |
| Alert/notification system | Defer to v3 |
| Sentiment forecasting/ML | Defer to v3+ |
| DeBERTa ABSA co-loading | Memory risk on Render; defer aspect model to separate batch job if needed |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | 05 | Complete |
| INFRA-02 | 05 | Complete |
| INFRA-03 | 05 | Complete |
| COLL-01 | — | Complete |
| COLL-02 | — | Complete |
| COLL-03 | — | Complete |
| COLL-04 | — | Complete |
| COLL-05 | — | Complete |
| COLL-06 | — | Complete |
| SENT-01 | — | Complete |
| SENT-02 | — | Complete |
| SENT-03 | — | Complete |
| SENT-04 | — | Complete |
| FRON-01 | — | Complete |
| FRON-02 | — | Complete |

**Coverage:**
- v2.0 requirements: 15 total
- Mapped to phases: 3
- Unmapped: 12 (traceability table update pending in Phase 10)

---
*Requirements defined: 2026-02-19*
*Last updated: 2026-02-19 after initial definition*
