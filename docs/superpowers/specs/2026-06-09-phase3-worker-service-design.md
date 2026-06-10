# Phase 3 — Worker Service: design decisions

Consume posts from RabbitMQ, run sentiment analysis, write results to
Postgres. This doc records the decisions and the reasoning; the phase plan
itself lives in the project goal.

## Consumer library: aio-pika (not pika)

`lib_db` is async-only (psycopg `AsyncConnection` / `AsyncConnectionPool`), so
a synchronous pika consumer would need `asyncio.run()` around every DB call —
an event loop spun up and torn down per message. With aio-pika the consumer
lives on one loop and the DB calls compose naturally.

The model is the opposite: synchronous and CPU-bound. It runs via
`asyncio.to_thread`, which keeps the loop responsive so AMQP heartbeats don't
time out during long inferences. `prefetch_count=1` because inference is the
bottleneck — buffering unacked messages in the consumer buys nothing and
widens the redelivery window on a crash.

## Message contract: self-contained post + tool slugs

```json
{
  "source": "reddit",
  "source_id": "t3_abc123",
  "content": "Cursor is great",
  "author": "alice",            // optional
  "url": "https://...",         // optional
  "published_at": "2026-06-01T12:00:00Z",  // ISO 8601, offset required
  "metadata": {},               // optional
  "tools": ["cursor"]           // non-empty; slugs must exist in `tools`
}
```

The message carries the full post rather than a DB id. Consequences:

- The worker owns the whole post → mention → analysis chain (the shape the
  Phase 1 design already sketched), in **one transaction per message** — a
  failure anywhere leaves no partial writes.
- A test message can be hand-published via the management UI with nothing
  pre-existing in the DB (the Phase 3 checkpoint).
- The future ingestion service stays decoupled from Postgres write order: it
  publishes and forgets.

Naive timestamps are refused rather than assumed UTC — guessing wrong would
silently shift posts across daily buckets.

## Idempotency: ride the natural keys

All three inserts are Scythe-generated idempotent insert-or-get on natural
keys (`(source, source_id)`, `(post_id, tool_id)`,
`(mention_id, model_name, model_version)`). Redelivering an already-processed
message re-runs inference but writes nothing new — no upsert logic needed in
the worker itself. `model_version` is the HF snapshot commit hash, so a model
upgrade produces new analysis rows instead of colliding with old verdicts.

## Error taxonomy: permanent vs transient

- **Permanent** (`PermanentError`): malformed JSON, missing/ill-typed fields,
  naive timestamp, unknown tool slug. Redelivery cannot fix these →
  `reject(requeue=False)` → dead-letter exchange `posts.dlx` → queue
  `posts.to_analyze.dead`, where the payload sits inspectable.
- **Transient** (everything else: DB down, network blip): `nack(requeue=True)`
  after a 5 s damper sleep — with prefetch=1 an immediate requeue would
  redeliver the same message in a hot loop for the whole outage.

Unknown tool slug is classed permanent deliberately: it's a contract violation
by the publisher. The alternative (requeue until someone seeds the tool) would
wedge the queue head on one bad message.

## Score semantics: [0, 1], matching the existing dashboard

`score = 0.5 + (P(positive) − P(negative)) / 2`, label = argmax. The seed and
demo data already use 0.9≈positive / 0.2≈negative on a [0,1] axis, and the
dashboard averages scores; this mapping keeps neutral at 0.5 and uses the full
probability mass (a 0.5 score can mean "confidently neutral" — the full
distribution is preserved in `raw_output` for later re-interpretation).

Model: `cardiffnlp/twitter-roberta-base-sentiment-latest` (3-class, trained on
social media text — the closest match to our sources). The worker only sees
`analyze(text) -> SentimentResult`, so swapping models is a one-class change.

## Docker: bake the model, run offline

The Dockerfile diverges from the API's structure in one way: dependencies are
synced from manifests only (`--no-install-workspace`) and the model snapshot
is downloaded *before* source code is copied, so the ~1 GB torch layer and
~500 MB model layer survive code-only rebuilds. At runtime `HF_HUB_OFFLINE=1`
pins the container to the baked snapshot — startup needs no network and can't
drift to a newer model revision without a rebuild.

torch resolves from the PyTorch CPU wheel index on Linux (the default PyPI
wheels bundle CUDA and weigh several GB); macOS PyPI wheels are CPU-only
already, so dev machines are unaffected.

## Out of scope (deferred)

- Retry budget / poison-message counters for transient failures (a message
  that fails transiently forever currently retries forever, 5 s apart).
- Batched inference; multiple consumers; observability beyond logs.
- The ingestion service (Phase 4) — it will publish to `posts.to_analyze`
  using this contract.
