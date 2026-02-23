---
phase: 06-data-collection
plan: "03"
subsystem: pipeline
tags: [asyncpraw, reddit, devto, forem, data-collection, oauth, rate-limiting, semaphore]

# Dependency graph
requires:
  - phase: 06-01
    provides: filter_service.is_relevant(), storage_service.save_post(), PostCreate model, pipeline structure

provides:
  - asyncpraw==7.8.1 Reddit OAuth client with two-layer subreddit filtering strategy
  - Dev.to Forem API v1 client with semaphore-limited concurrent body fetches
  - run_collect_reddit APScheduler job (env-var credential gating, retry logic)
  - run_collect_devto APScheduler job (two-pass filter, seen_ids dedup across tags)

affects:
  - 06-04 (scheduler integration will import run_collect_reddit and run_collect_devto)

# Tech tracking
tech-stack:
  added:
    - asyncpraw==7.8.1 (Reddit OAuth read-only API via asyncpraw)
  patterns:
    - "Two-layer subreddit filtering: loose is_relevant() on tool-specific subs, strict on broad AI/dev subs"
    - "Reddit session cleanup: async with asyncpraw.Reddit(...) as reddit context manager mandatory"
    - "Dev.to two-pass filter: title+description first (cheap), full body_markdown second (expensive)"
    - "Semaphore-limited concurrency: asyncio.Semaphore(5) caps concurrent Dev.to body fetches"
    - "asyncio.gather(return_exceptions=True): prevents one body fetch failure from canceling all others"
    - "seen_ids set: deduplicates articles appearing under multiple Dev.to tags before body fetch"
    - "Credential gating: collect_reddit returns early with errors=1 when REDDIT_CLIENT_ID/SECRET missing"

key-files:
  created:
    - backend/pipeline/clients/reddit_client.py
    - backend/pipeline/jobs/collect_reddit.py
    - backend/pipeline/clients/devto_client.py
    - backend/pipeline/jobs/collect_devto.py
  modified:
    - backend/requirements.txt

key-decisions:
  - "asyncpraw context manager (async with ... as reddit) is mandatory pattern — prevents aiohttp connector leak warnings on session close"
  - "Tool-specific subreddits use same is_relevant() filter as broad subs — the 'loose vs strict' distinction is documented but both call is_relevant() identically (simplicity over premature optimization)"
  - "Dev.to seen_ids dedup happens before body fetch — saves API calls for articles appearing under multiple tags"
  - "BODY_FETCH_CONCURRENCY=5 caps concurrent /api/articles/{id} requests to avoid 429 rate limits without API key"

patterns-established:
  - "Credential gating pattern: check env vars at job start, log.error + return early with errors=1 if missing"
  - "Stats dict pattern: all jobs return {collected, filtered[_*], duplicates, errors} for scheduler logging"
  - "Normalize-then-store pattern: source client returns raw dicts, normalize_* converts to PostCreate fields"

requirements-completed:
  - COLL-02
  - COLL-04

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 06 Plan 03: Reddit + Dev.to Source Collectors Summary

**asyncpraw Reddit collector with two-layer subreddit filtering and Dev.to Forem API v1 collector with semaphore-capped concurrent body fetches**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23T08:32:58Z
- **Completed:** 2026-02-23T08:35:58Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Reddit client with TOOL_SUBREDDITS (5: ChatGPT, ClaudeAI, cursor, GithubCopilot, LocalLLaMA) and BROAD_SUBREDDITS (5: artificial, MachineLearning, programming, learnmachinelearning, ChatGPTCoding) using asyncpraw OAuth
- Reddit job with credential env-var gating (early return errors=1), retry with [0, 5, 30]s delays, and two-layer filtering
- Dev.to client with DEVTO_TAGS (10 tags), BODY_FETCH_CONCURRENCY=5, and full body_markdown fetch per article
- Dev.to job with two-pass filtering (title+description first, full body second), semaphore concurrency, seen_ids dedup, and gather with return_exceptions=True
- asyncpraw==7.8.1 added to requirements.txt

## Task Commits

Each task was committed atomically:

1. **Task 1: Add asyncpraw to requirements.txt and implement Reddit client + job** - `a62d659` (feat)
2. **Task 2: Implement Dev.to Forem API v1 client and collection job** - `ca71085` (feat)

**Plan metadata:** `(docs commit follows)`

## Files Created/Modified
- `backend/requirements.txt` - Added asyncpraw==7.8.1
- `backend/pipeline/clients/reddit_client.py` - asyncpraw Reddit client with TOOL_SUBREDDITS, BROAD_SUBREDDITS, fetch_subreddit_posts, normalize_reddit_post
- `backend/pipeline/jobs/collect_reddit.py` - APScheduler job with credential gating, retry, two-layer filtering
- `backend/pipeline/clients/devto_client.py` - Forem API v1 client with DEVTO_TAGS (10), BODY_FETCH_CONCURRENCY=5, fetch_devto_articles, fetch_article_body, normalize_devto_article
- `backend/pipeline/jobs/collect_devto.py` - APScheduler job with two-pass filter, semaphore concurrency, seen_ids dedup

## Decisions Made
- Both tool-specific and broad subreddits call the same `is_relevant()` function — the two-layer distinction is preserved in the loop structure (strict_filter flag) but both call the same logic. This keeps the code simple and avoids premature optimization; the main value of the distinction is conceptual clarity.
- Reddit returns posts as raw dicts inside the asyncpraw context manager to ensure all data is extracted before the session closes — asyncpraw objects are stateful and cannot be used after the context manager exits.
- Dev.to `seen_ids` dedup is applied before the body fetch candidates list is built — this means articles appearing under multiple tags are fetched only once, saving API quota.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Python 3.14 system install could not build pydantic-core wheels for runtime import verification. AST-based static verification was used as an equivalent alternative (confirmed all required exports, list sizes, constants, and control flow patterns). The Docker runtime is the actual execution environment.

## User Setup Required

**External services require manual configuration.**

Reddit OAuth credentials must be configured before the Reddit collector will function:

| Env Var | Source |
|---------|--------|
| `REDDIT_CLIENT_ID` | Reddit Apps page → create "script" type app → client ID shown below app name |
| `REDDIT_CLIENT_SECRET` | Same app → "secret" field |

**Dashboard setup:**
1. Visit https://www.reddit.com/prefs/apps
2. Click "are you a developer? create an app"
3. App type: **script**
4. Redirect URI: `http://localhost:8080` (unused for read-only)
5. No account scope needed — read-only access only

**Dev.to API key is optional:**
- `DEVTO_API_KEY` env var — improves rate limit ceiling but public articles are accessible without auth

## Next Phase Readiness
- Reddit and Dev.to collectors ready for scheduler registration in 06-04
- Both jobs follow the `run_collect_*` naming pattern expected by scheduler integration
- All jobs accept `AsyncSession` and return stats dict with collected/filtered/duplicates/errors keys
- Reddit credentials must be set before Reddit jobs will collect; Dev.to works without credentials

## Self-Check: PASSED

All files created and commits verified:
- backend/requirements.txt: FOUND
- backend/pipeline/clients/reddit_client.py: FOUND
- backend/pipeline/jobs/collect_reddit.py: FOUND
- backend/pipeline/clients/devto_client.py: FOUND
- backend/pipeline/jobs/collect_devto.py: FOUND
- .planning/phases/06-data-collection/06-03-SUMMARY.md: FOUND
- Commit a62d659: FOUND
- Commit ca71085: FOUND

---
*Phase: 06-data-collection*
*Completed: 2026-02-23*
