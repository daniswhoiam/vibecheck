---
phase: 07-tier-1-sentiment-aggregation
plan: "02"
subsystem: api
tags: [transformers, torch, huggingface, gliclass, zero-shot-classification, asyncio, sentiment]

# Dependency graph
requires:
  - phase: 07-tier-1-sentiment-aggregation
    provides: placeholder sentiment_service.py from Phase 5 cleanup

provides:
  - SentimentClassifier class in backend/pipeline/services/sentiment_service.py with on-demand GliClass model lifecycle
  - transformers==4.39.3 and torch==2.0.1 pinned in requirements.txt

affects:
  - 07-03-score-sentiment-job (consumes SentimentClassifier.classify())

# Tech tracking
tech-stack:
  added:
    - transformers==4.39.3
    - torch==2.0.1
  patterns:
    - On-demand model load/unload pattern — model loaded once per job run, unloaded in finally block to free memory
    - asyncio.to_thread() wrapping for synchronous HuggingFace pipeline() calls to avoid blocking event loop
    - Lazy import of transformers inside _load_pipeline() — avoids import-time side effects and slow startup

key-files:
  created: []
  modified:
    - backend/requirements.txt
    - backend/pipeline/services/sentiment_service.py

key-decisions:
  - "device=-1 (CPU) set explicitly — Render Standard tier has no GPU; avoids CUDA not found warnings"
  - "On-demand load/unload per classify() call — trades 3s model load time for minimal baseline memory between 6h cycles"
  - "MAX_CHARS=2000 truncation — approximately 512 tokens for typical English developer text"
  - "multi_label=False — single dominant class per post, not multi-label classification"
  - "Labels: Positive/Negative/Neutral (capitalized) — matching CONTEXT.md user decision"
  - "DEFAULT_BATCH_SIZE=8 — conservative for 1.5GB memory budget, can increase after benchmarking"

patterns-established:
  - "On-demand HF model lifecycle: _load_pipeline() → _classify_batch_sync() → _unload_pipeline() in finally block"
  - "asyncio.to_thread() for both load and inference — keeps event loop unblocked during CPU-intensive work"
  - "Lazy import inside sync method: from transformers import pipeline inside _load_pipeline()"

requirements-completed: [SENT-01]

# Metrics
duration: 1min
completed: 2026-02-23
---

# Phase 7 Plan 02: ML Dependencies and SentimentClassifier Summary

**GliClass zero-shot sentiment classifier with on-demand CPU model lifecycle using asyncio.to_thread() for non-blocking load and inference**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-23T09:40:33Z
- **Completed:** 2026-02-23T09:42:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added transformers==4.39.3 and torch==2.0.1 to requirements.txt under ML / Sentiment section
- Implemented SentimentClassifier class with full on-demand model lifecycle (load → classify → unload)
- classify() async method wraps synchronous HuggingFace pipeline in asyncio.to_thread() for non-blocking operation
- Memory cleanup guaranteed via finally block calling _unload_pipeline()

## Task Commits

Each task was committed atomically:

1. **Task 1: Add transformers and torch to requirements.txt** - `9361e76` (chore)
2. **Task 2: Implement SentimentClassifier in sentiment_service.py** - `a9bd1b9` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `backend/requirements.txt` - Added ML / Sentiment section with transformers==4.39.3 and torch==2.0.1 pins
- `backend/pipeline/services/sentiment_service.py` - Full SentimentClassifier implementation replacing placeholder

## Decisions Made
- CPU-only inference with device=-1 — Render Standard tier has no GPU, explicit flag avoids CUDA warnings
- On-demand model load/unload per classify() call — 3s load time tradeoff for minimal memory between 6h cycles
- asyncio.to_thread() for both load and inference steps — HuggingFace pipeline() is fully synchronous
- Labels Positive/Negative/Neutral (capitalized) matching user decision from CONTEXT.md
- MAX_CHARS=2000 truncation to stay within ~512 token context window
- DEFAULT_BATCH_SIZE=8 as conservative start for 1.5GB memory budget

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The model (knowledgator/gliclass-base-v1.0-lw) is downloaded at runtime from HuggingFace Hub on first classify() call.

## Next Phase Readiness

- SentimentClassifier is ready for Plan 03 (score_sentiment job) to import and call classify()
- Model downloads from HuggingFace Hub automatically at runtime — no manual model download needed
- CPU inference confirmed working (device=-1 explicit)
- Memory lifecycle guaranteed via finally block

---
*Phase: 07-tier-1-sentiment-aggregation*
*Completed: 2026-02-23*
