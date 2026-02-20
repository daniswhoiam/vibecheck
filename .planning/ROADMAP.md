# Roadmap: VibeCheck

## Milestones

- ✅ **v1.0 MVP** — Phases 1-3.1 (shipped 2026-02-19)
- 🚧 **v2.0 Free Pipeline** — Phases 5-9 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-3.1) — SHIPPED 2026-02-19</summary>

- [x] Phase 1: Foundation & Storage (3/3 plans) — completed 2026-02-05
- [x] Phase 2: Data Pipeline (4/4 plans) — completed 2026-02-05
- [x] Phase 3: API & Integration (3/3 plans) — completed 2026-02-05
- [x] Phase 3.1: Entity Seeding Automation (1/1 plan) — completed 2026-02-05

</details>

### 🚧 v2.0 Free Pipeline (In Progress)

**Milestone Goal:** Replace the $250/mo AskNews API with five free data sources and a self-hosted/cheap sentiment pipeline, while evolving the frontend to display richer aspect-level sentiment data.

#### Phase Checklist

- [x] **Phase 5: Infrastructure** — Schema migration, dependency cleanup, and Render upgrade
- [ ] **Phase 6: Data Collection** — All five free source collectors wired in with filtering and deduplication
- [ ] **Phase 7: Tier 1 Sentiment + Aggregation** — RoBERTa pipeline running, aggregation job writing per-source timeseries, API extended
- [ ] **Phase 8: Tier 2 LLM + Aspect Extraction** — LLM layer extracting aspect-level sentiment for high-value posts
- [ ] **Phase 9: Frontend Evolution** — Source breakdown and aspect charts surfaced in UI

## Phase Details

### Phase 5: Infrastructure
**Goal**: The codebase is clean of AskNews, the database schema supports the new pipeline, and Render is provisioned to handle ML workloads
**Depends on**: Nothing (first v2.0 phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03
**Success Criteria** (what must be TRUE):
  1. Alembic migration creates posts, post_entity_mentions, and aspect_sentiments tables without dropping any existing tables
  2. AskNews SDK is removed from requirements.txt and httpx is upgraded to 0.28.1 with no import errors on startup
  3. Render Standard tier is live and the app starts and serves requests successfully
  4. Existing API endpoints return correct data after migration (backward compatibility confirmed)
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md — Schema reset: TimescaleDB image, destructive Alembic migration, new ORM models, env.py fixes
- [x] 05-02-PLAN.md — AskNews removal: delete 4 files, clean 7 pipeline files, update requirements.txt

### Phase 6: Data Collection
**Goal**: Posts from Hacker News, Reddit, Discourse, and Dev.to are flowing into the database on a schedule, with irrelevant posts filtered and duplicates rejected
**Depends on**: Phase 5
**Requirements**: COLL-01, COLL-02, COLL-03, COLL-04, COLL-05, COLL-06
**Success Criteria** (what must be TRUE):
  1. New posts appear in the posts table after each scheduled collection run, with source field identifying origin
  2. A post queried via the API with a known irrelevant keyword does not appear in the database
  3. Submitting the same URL or content twice results in exactly one stored post (deduplication confirmed)
  4. Collection job completes without aborting when one source is unavailable
**Plans**: 4 plans

Plans:
- [ ] 06-01-PLAN.md — Shared foundation: PostCreate model, FilterService (ambiguity-aware), StorageService with dedup
- [ ] 06-02-PLAN.md — HN Algolia + Discourse REST collectors (Wave 2, parallel with 06-03)
- [ ] 06-03-PLAN.md — Reddit asyncpraw + Dev.to Forem API collectors (Wave 2, parallel with 06-02)
- [ ] 06-04-PLAN.md — Scheduler wiring: setup_jobs() with 4 staggered jobs + end-to-end verification

### Phase 7: Tier 1 Sentiment + Aggregation
**Goal**: Every collected post has a RoBERTa sentiment score, sentiment_timeseries rollups include per-source breakdown, and the API exposes source breakdown data to consumers
**Depends on**: Phase 6
**Requirements**: SENT-01
**Success Criteria** (what must be TRUE):
  1. All posts in the database have a non-null roberta_score after the sentiment job runs
  2. The sentiment_timeseries table contains a source_breakdown JSONB column populated with per-source sentiment values
  3. The entity sentiment history endpoint returns a source_breakdown field alongside existing fields
  4. Render memory usage stays below 1.5GB under sustained sentiment job load (no OOM restarts)
**Plans**: TBD

### Phase 8: Tier 2 LLM + Aspect Extraction
**Goal**: Posts with ambiguous or non-neutral Tier 1 scores are processed by the configured LLM and aspect-level sentiment is stored per tool mention
**Depends on**: Phase 7
**Requirements**: SENT-02, SENT-03, SENT-04
**Success Criteria** (what must be TRUE):
  1. Posts routed to Tier 2 have aspect_sentiments rows covering at least one of the seven defined aspects (performance, cost, reliability, UX, speed, code quality, context window)
  2. Changing the LLM_PROVIDER env var to a different provider (Groq, DeepInfra, GPT-4o-mini) results in the new provider handling Tier 2 requests without code changes
  3. A new entity aspect endpoint returns aspect scores when queried for an entity with accumulated Tier 2 data
**Plans**: TBD

### Phase 9: Frontend Evolution
**Goal**: Users can see which data sources are driving sentiment and can explore aspect-level breakdowns per entity
**Depends on**: Phase 7, Phase 8
**Requirements**: FRON-01, FRON-02
**Success Criteria** (what must be TRUE):
  1. User can select a source filter (HN, Reddit, Discourse, Dev.to) on the entity detail page and the sentiment chart updates to reflect only that source
  2. User can view an aspect sentiment chart for an entity showing scores across the seven defined aspects
  3. Existing entity list and sentiment trend views still load and display correct data with no visible regressions
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & Storage | v1.0 | 3/3 | Complete | 2026-02-05 |
| 2. Data Pipeline | v1.0 | 4/4 | Complete | 2026-02-05 |
| 3. API & Integration | v1.0 | 3/3 | Complete | 2026-02-05 |
| 3.1. Entity Seeding Automation | v1.0 | 1/1 | Complete | 2026-02-05 |
| 5. Infrastructure | v2.0 | 2/2 | Complete | 2026-02-19 |
| 6. Data Collection | v2.0 | 0/4 | Not started | - |
| 7. Tier 1 Sentiment + Aggregation | v2.0 | 0/? | Not started | - |
| 8. Tier 2 LLM + Aspect Extraction | v2.0 | 0/? | Not started | - |
| 9. Frontend Evolution | v2.0 | 0/? | Not started | - |

---
*Roadmap created: 2026-02-05*
*Last updated: 2026-02-19 (v2.0 milestone phases added)*
