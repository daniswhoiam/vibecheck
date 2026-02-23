# Phase 7: Tier 1 Sentiment + Aggregation - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Every collected post gets a sentiment classification score, sentiment rollups include per-source breakdown, and the API exposes source breakdown data. This phase replaces the v1.0 SentimentTimeseries model with a new aggregation table and cleans up all v1.0 remnants.

</domain>

<decisions>
## Implementation Decisions

### Scoring strategy
- Use GliClass (zero-shot classification) instead of RoBERTa
- 3-class labels: Positive / Negative / Neutral
- Score using post body text (title + body), truncated if needed for model token limits
- Only process new/unscored posts (where sentiment columns are NULL) — not full rescore
- Incremental: each run processes only posts that haven't been scored yet

### Aggregation rollups
- Replace the v1.0 SentimentTimeseries concept entirely — new table, clean break
- Incremental aggregation: only recompute the current day's bucket each run
- Stats per rollup row: mean sentiment + post count, broken down per source
- Source breakdown stored as JSONB (e.g. `{hn: {mean: 0.4, count: 12}, reddit: {mean: -0.1, count: 8}}`)

### API changes
- Rewrite existing `/entities/{id}/sentiment` endpoint to query new rollup table — same URL, new response shape
- Source breakdown nested inside each timeseries data point (one call gets everything)
- Clean up ALL v1.0 remnants in Phase 7: remove dead Article/SentimentTimeseries imports from db/__init__.py, fix entity routes that reference old models, update schemas

### Pipeline chaining
- Chain: collect → score → aggregate as one pipeline per source
- Sentiment scoring runs after each collection job completes, not on a separate schedule
- Aggregation runs after scoring completes — data always consistent

### Claude's Discretion
- Sentiment storage format on Post model (label + confidence vs numeric score — pick what best supports aggregation and Tier 2 routing)
- Time granularity for rollups (daily only vs hourly+daily — pick based on 6-hour collection cycles)
- GliClass model loading strategy (on-demand vs resident — pick based on model size and typical deployment memory constraints, not Render-specific)
- Batch size for sentiment processing (pick based on model memory profile)
- Whether entity list endpoint includes latest sentiment score

</decisions>

<specifics>
## Specific Ideas

- User explicitly chose GliClass over RoBERTa — this is a zero-shot approach where we define labels
- Memory strategy should be based on general deployment constraints, not Render-specifically
- The pipeline chain (collect → score → aggregate) should feel like one cohesive operation per source

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-tier-1-sentiment-aggregation*
*Context gathered: 2026-02-23*
