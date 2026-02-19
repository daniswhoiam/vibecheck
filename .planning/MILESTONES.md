# Milestones

## v1.0 MVP (Shipped: 2026-02-19)

**Phases completed:** 4 phases, 11 plans
**Lines of code:** 3,347 Python (backend)
**Git range:** feat(01-01) → feat(03.1-01)

**Key accomplishments:**
- Docker Compose environment with PostgreSQL, FastAPI, health checks, and auto-migrations
- SQLAlchemy 2.0 async ORM models with TimescaleDB-compatible time-series schema
- AskNews SDK integration with OAuth2 auth and entity normalization (50+ variations)
- Scheduled data pipeline: news every 15min, stories every 60min, with retry and deduplication
- REST API with entity endpoints, sentiment time-series with cursor pagination, environment-aware CORS
- Automated entity seeding on FastAPI startup (critical E2E gap closed via Phase 3.1)

---

