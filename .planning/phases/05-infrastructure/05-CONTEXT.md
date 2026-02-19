# Phase 5: Infrastructure - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Clean the codebase of all AskNews dependencies, design and create the new database schema for the free multi-source pipeline, and prepare the codebase for deployment on a new (non-Render) hosting platform. This phase does NOT include actual deployment to the new platform — that is a separate effort.

</domain>

<decisions>
## Implementation Decisions

### Post data model
- Content storage level: Claude's discretion (pick based on what sentiment analysis needs)
- Engagement metrics: Claude's discretion (raw vs. normalized — pick the practical approach)
- No author/PII storage — posts are anonymous (no username, no profile URL)
- Entity relationships: many-to-many via post_entity_mentions table (a post can mention multiple entities)

### Aspect sentiment categories
- Initial set of 7 aspects from research: performance, cost, reliability, UX, speed, code quality, context window — Claude may refine based on what sources actually discuss
- Storage format: hardcoded enum vs. reference table — Claude's discretion
- Score type: numeric float scale (-1.0 to 1.0), NOT categorical labels
- Score only per aspect — no evidence text snippets stored

### Existing data handling
- Full wipe: drop ALL existing data (articles, sentiment_timeseries, entities)
- No backup needed — data is not valuable enough to preserve
- Fresh start: entities will be re-seeded in a later phase
- This means Alembic migrations can be destructive — no need for additive-only strategy

### Hosting and deployment
- Leave Render entirely — no Render dependency going forward
- Phase 5 scope is codebase-only: schema, dependencies, code cleanup
- Actual deployment to new platform is out of scope for this phase
- Research phase should investigate cheapest hosting (Oracle Cloud free tier, Fly.io, Railway, HF Spaces, etc.) using the external research doc as input
- No downtime concerns since we're doing a fresh deploy on a new platform

### Database extensions
- Include TimescaleDB for time-series partitioning and continuous aggregates
- Include pgvector for embedding storage and semantic search
- Schema should leverage hypertables and vector columns from the start

### Claude's Discretion
- Post content storage depth (title+snippet vs. full body)
- Engagement metric design (raw vs. normalized vs. both)
- Aspect list refinement (the 7 aspects are a starting point, not locked)
- Aspect storage mechanism (enum vs. reference table)
- Schema details that align with the external research doc recommendations (posts, sentiment_scores, tool_mentions pattern)

</decisions>

<specifics>
## Specific Ideas

- External research document (`sentiment_analysis_improvement.md` in project root) should guide schema design — it recommends: `posts` hypertable, `sentiment_scores` table, `tool_mentions` table with aspect scores
- The research doc's schema pattern (source, URL, title, body, metadata as JSONB, content_hash, embedding as VECTOR(384)) should be considered as the baseline
- TimescaleDB continuous aggregates for pre-computing daily averages per tool per source
- Content hash (SHA-256) column for deduplication support in later phases

</specifics>

<deferred>
## Deferred Ideas

- PII masking during post ingestion — belongs in Phase 6 (Data Collection) since that's when posts are processed before storage
- Actual deployment to new hosting platform — separate effort after codebase is ready
- Entity re-seeding — later phase after schema is established

</deferred>

---

*Phase: 05-infrastructure*
*Context gathered: 2026-02-19*
