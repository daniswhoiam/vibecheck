# Phase 4 — Ingestion Service: design decisions

Poll Hacker News and Reddit for posts about tracked tools, detect which tools
each post mentions, and publish them to `posts.to_analyze` using the Phase 3
message contract. This doc records the decisions and the reasoning; the phase
plan itself lives in the project goal.

## Shape: async service, sync sources wrapped

The repo's I/O layer is async (lib_db is psycopg-async, the broker client is
aio-pika), so the service runs on one asyncio loop like the worker. The two
sources differ:

- **HN Algolia** is a plain HTTP API → `httpx.AsyncClient`, natively async.
- **Reddit via PRAW** is synchronous → each fetch runs in `asyncio.to_thread`,
  the same pattern the worker uses for CPU-bound inference. asyncpraw exists,
  but the sync library behind a thread is one moving part fewer (no async
  session lifecycle to manage) and the call is coarse-grained — one thread hop
  per fetch cycle, not per request.

## Fetch strategy: search per tool, then detect locally

Two candidate strategies for each source:

1. **Scan the firehose** (newest posts) and run our own tool detection over
   everything. One request per source/subreddit, but misses everything that
   scrolls past between polls in high-volume venues, and most fetched posts
   are irrelevant.
2. **Search per tool** using the source's own search. Finds mentions even in
   high-volume venues; the result set is pre-filtered, so volume is small.

We search per tool (strategy 2), one query per tool using its display name:

- **HN**: `search_by_date` with `tags=story` and
  `numericFilters=created_at_i>cutoff`, where the cutoff is a configurable
  lookback window. Stories only for now — comments are a different beast
  (volume, threading) and the goal scopes Phase 4 to posts.
- **Reddit**: `subreddit("a+b+c").search(query, sort="new")` over the
  configured subreddit list — PRAW's combined-subreddit syntax keeps it to one
  search per tool rather than tools × subreddits.

Detection still runs on every hit, for two reasons: a post found by searching
"Cursor" may also mention Copilot (one post → several tool slugs, which is
exactly what the worker's mention chain expects), and search is fuzzier than
our word-boundary rules (Algolia tokenizes loosely; a hit is not necessarily a
real mention).

## Tool detection: DB aliases + word boundaries, with negative patterns

The `tools` table is already the registry (slug, display_name, aliases) — the
matcher is built from `list_tools()` at the start of each cycle, so seeding a
new tool requires no ingestion deploy.

Matching rules, in order:

1. **Negative patterns first**: a small hardcoded map of phrases that *look*
   like a tool but aren't — "Microsoft Copilot", "Copilot Studio", "M365
   Copilot" must not count as GitHub Copilot. Matching spans are blanked out
   of the text before alias matching, so "Microsoft Copilot is not GitHub
   Copilot" still detects the genuine mention. Hardcoded (not in the DB)
   because it is matcher logic, not registry data; it moves to the DB if it
   ever needs per-deployment tuning.
2. **Alias matching**: each alias becomes a case-insensitive, word-boundary
   regex. Word boundaries give the right answers for the goal's edge cases:
   `gpt` does not fire inside "ChatGPT" (no boundary between *t* and *g*), but
   "GPT-4" does contain the word `gpt`. Multi-word aliases tolerate flexible
   whitespace.

False positives are inherent at this fidelity ("cursor" the English word) —
acceptable because the per-tool search already biases the corpus toward posts
about the tool, and sentiment over a large sample tolerates noise. Smarter
disambiguation (NER, context windows) is deliberately out of scope.

## Dedup: DB check as optimization, worker idempotency as correctness

Polling with a lookback window re-fetches mostly the same posts every cycle.
Two layers:

- **Correctness** already exists: the worker's inserts are idempotent
  insert-or-get on `(source, source_id)` — a duplicate message is a no-op.
- **Optimization** added here: before publishing, a `PostExists` query skips
  posts already in `posts`. Without it, every cycle would re-run model
  inference (seconds of CPU per post) on the whole lookback window.

The race in between — a post published but not yet processed when the next
cycle fetches it again — lands a duplicate message, which the worker's
idempotency absorbs. So the DB check does not need to be (and is not)
transactionally precise. No in-process seen-set: the DB already remembers,
and state in the process would be lost on restart anyway.

## Publishing: same topology declaration, contract by construction

The publisher declares the same queue + DLX topology as the worker
(`posts.to_analyze`, `posts.dlx`, `posts.to_analyze.dead`). This is not
optional duplication: RabbitMQ rejects a re-declaration whose arguments differ
(`PRECONDITION_FAILED`), so whichever service starts first must declare the
queue with the *identical* `x-dead-letter-*` arguments. The names and
arguments are mirrored in `ingestion/publisher.py` with a pointer at
`worker/consumer.py`; a shared `lib/mq` package would couple the services'
deployments to save ~15 lines, and the worker's contract tests already pin
the wire format — not worth it at two services.

Messages are JSON per the Phase 3 contract (`source`, `source_id`, `content`,
`published_at` with offset, non-empty `tools`, optional `author`/`url`/
`metadata`) and published with `delivery_mode=PERSISTENT` so a broker restart
does not drop accepted posts. Source-specific extras (points, subreddit,
num_comments) ride in `metadata`.

Tool slugs in a message always come from the matcher, which was built from
the same DB the worker resolves slugs against — an unknown-slug dead-letter
can only happen if a tool is deleted mid-flight.

## Scheduling: a plain interval loop

One job, one interval → `while True: run_cycle(); await asyncio.sleep(...)`.
APScheduler earns its keep with multiple schedules, cron semantics, jitter, or
persistence — none of which Phase 4 needs; YAGNI. A cycle failure (source
down, broker hiccup) is logged and the loop sleeps and retries — the service
must outlive its dependencies' bad days, never crash-loop on them.

Config via environment, like the other services:

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | local dev DSN | tools registry + dedup checks |
| `AMQP_URL` | local dev URL | publish target |
| `INGEST_INTERVAL_SECONDS` | `300` | sleep between cycles |
| `INGEST_LOOKBACK_SECONDS` | `3600` | search window (overlap is fine — dedup) |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT` | unset | Reddit fetcher is **disabled** unless all are set |
| `REDDIT_SUBREDDITS` | curated dev list | comma-separated, searched combined |

The lookback window means the service is stateless across restarts: it
re-covers the window and dedup drops what it already published. No cursor to
persist, no Redis dependency yet.

## Testing

- **Detection**: pure unit tests — the goal's edge cases (GPT vs ChatGPT,
  Copilot disambiguation) plus word-boundary and multi-alias cases.
- **Fetchers**: HN via `httpx.MockTransport` (no network); Reddit via a stub
  PRAW object — both test the *mapping* to canonical posts, not the vendors.
- **Publisher**: against the real broker (CI already runs RabbitMQ) with
  throwaway queue names, same isolation trick as the worker's consumer tests;
  asserts a published message round-trips through the worker's own
  `parse_post_message`, pinning the contract from both ends.
- **Pipeline**: stub fetchers + real Postgres for the dedup path.

## Docker

Mirrors the API's Dockerfile (uv sync of one package, unprivileged user) — no
model to bake, nothing exotic. Compose service depends on healthy postgres +
rabbitmq, with Reddit credentials passed through from the host environment
(absent locally → HN-only, by design).

## Out of scope (deferred)

- HN/Reddit comments; more sources (the fetcher interface is the seam).
- Cursor-based incremental fetching (lookback + dedup is simpler and
  self-healing); Redis stays unused.
- Rate-limit backoff beyond PRAW's built-in throttling and polite intervals.
- Negative-pattern registry in the DB; smarter disambiguation than word
  boundaries.
