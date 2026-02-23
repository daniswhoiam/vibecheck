# Phase 8: Tier 2 LLM + Aspect Extraction - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Posts with low-confidence Tier 1 scores are processed by a configurable LLM to extract aspect-level sentiment per entity mention, stored in the existing `aspect_sentiments` table. A new API endpoint exposes aggregated aspect data per entity. The seven aspects are fixed: performance, cost, reliability, UX, speed, code quality, context window.

</domain>

<decisions>
## Implementation Decisions

### Routing criteria
- Only posts with Tier 1 confidence < 0.6 are routed to Tier 2 (strict threshold)
- ALL labels eligible: Positive, Negative, AND Neutral with low confidence
- This catches misclassified Neutral posts that may contain strong opinions
- Posts not meeting the threshold keep their Tier 1 label with no Tier 2 processing

### LLM prompt & output
- Structured JSON output enforced via provider's JSON mode / function calling
- LLM must link each aspect score to a SPECIFIC entity mentioned in the post (not broadcast to all)
- Prompt provides the post text + list of entity names mentioned, LLM returns per-entity aspect scores
- Score range: -1.0 (very negative) to 1.0 (very positive), matching AspectSentiment schema

### Provider configuration
- Default provider: Groq
- Default model: Llama 3.3 70B (strongest open model available, good JSON mode support)
- Provider switchable via `LLM_PROVIDER` env var without code changes (Groq, DeepInfra, GPT-4o-mini)
- Model switchable via `LLM_MODEL` env var

### Failure handling
- Retry 2-3 times with exponential backoff on provider failure (rate limit, timeout, error)
- After retries exhausted, mark post as failed and move on (no data loss, retried next run)
- No fallback to secondary provider — keep it simple

### Aspect endpoint
- New endpoint: entity aspect scores with aggregated averages AND time series data
- Fixed time windows: 7d, 30d, 90d (not arbitrary date ranges)
- Include post count per aspect (how many posts contributed to each score)
- Support optional source filter param (HN, Reddit, Discourse, Dev.to)

### Claude's Discretion
- Per-run volume cap on LLM calls (consider provider rate limits and expected post volume)
- Whether LLM overrides Tier 1 overall sentiment label or only adds aspects
- Handling posts where LLM finds no relevant aspects (store nothing vs. store generic 'overall')
- Daily/monthly cost guardrails (rely on free tier limits vs. explicit cap)

</decisions>

<specifics>
## Specific Ideas

- Groq free tier has rate limits that serve as a natural throttle — research exact limits during planning
- The existing AspectSentiment table already has the right schema (post_id, entity_id, aspect, score with -1 to 1 range)
- PostEntityMention junction table already links posts to entities — leverage this for routing

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-tier-2-llm-aspect-extraction*
*Context gathered: 2026-02-23*
