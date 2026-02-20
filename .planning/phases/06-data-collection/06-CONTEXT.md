# Phase 6: Data Collection - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Collect developer posts from four free sources (Hacker News, Reddit, Discourse, Dev.to) into the posts table on a recurring schedule. Filter irrelevant posts via keyword matching and reject duplicates via content hashing. Sentiment analysis, aspect extraction, and frontend display are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Collection targets
- Research top 10 AI tools/models by usage (Kilo Code stats as starting reference) to drive keyword lists
- Reddit: two-layer approach — tool-specific subreddits (r/ChatGPT, r/ClaudeAI, r/cursor, etc.) plus broad AI/dev subs (r/artificial, r/LocalLLaMA, etc.) with stricter filtering on broad subs
- Discourse: Claude's discretion on which forums to target — research which AI tool Discourse forums are active and worth collecting from (Cursor and OpenAI mentioned as starting points)
- Hacker News: stories + top-level comments on relevant stories via Algolia API
- Dev.to: full articles via Forem API v1, filtered by relevant tags/keywords

### Filtering strictness
- Adaptive approach: start strict, loosen if data volume is insufficient
- Ambiguity-aware keyword matching: unambiguous tool names (ChatGPT, Copilot, GPT-4) match bare; ambiguous names (Claude, Cursor) require nearby context words (AI, model, coding, LLM, etc.)
- Exact deduplication only for v2.0: URL match + content hash. Near-duplicate detection (MinHash) deferred to COLL-10
- Rejected post handling: Claude's discretion on whether to log or silently discard based on storage/complexity tradeoffs

### Collection frequency
- Every 6 hours for all sources
- Sources staggered ~30 minutes apart to smooth resource usage
- On first run: backfill as much historical data as each free API allows
- Retry behavior on failure: Claude's discretion based on each API's characteristics

### Post content scope
- Store full text with a reasonable maximum character cap (Claude determines ceiling)
- Include top-level comments from Reddit and HN (not full threads)
- Dev.to: fetch and store full article body, not just excerpt
- Engagement metrics captured: upvotes, score, comment count (where available per source)
- No author/user identification data — defer to future phase
- GDPR compliance: strip or avoid storing any PII from collected posts

### Claude's Discretion
- Exact Discourse forums to target (research which are active)
- Reasonable max character cap for post content
- Retry strategy per source on failure
- Whether to log rejected posts or silently discard
- Specific subreddit list (tool-specific + broad, based on research)
- Stagger timing between sources

</decisions>

<specifics>
## Specific Ideas

- Kilo Code has usage statistics that could inform top 10 tool/model selection
- Two-layer Reddit strategy: narrow tool-specific subs get loose filtering, broad AI subs get strict filtering
- Ambiguity-aware matching is key — "Claude" and "Cursor" are common words outside AI context

</specifics>

<deferred>
## Deferred Ideas

- Near-duplicate detection (MinHash similarity) — already tracked as COLL-09 in Future Requirements
- Author credibility weighting — deferred until PII/GDPR strategy is fully defined
- Per-source frequency tuning — start uniform at 6h, adjust based on production volume data

</deferred>

---

*Phase: 06-data-collection*
*Context gathered: 2026-02-20*
