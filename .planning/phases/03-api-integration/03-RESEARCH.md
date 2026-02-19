# Phase 3: API & Integration - Research

**Researched:** 2026-02-05
**Domain:** REST API development with FastAPI, PostgreSQL, and React integration
**Confidence:** HIGH (based on current best practices and official documentation)

## Summary

Phase 3 requires implementing REST API endpoints for querying entity sentiment data with proper error handling, CORS configuration for React frontend integration, and efficient time-series data retrieval. The research reveals well-established patterns for FastAPI async development, PostgreSQL connection pooling, and modern frontend-backend integration.

**Primary recommendation:** Use FastAPI's async-first architecture with SQLAlchemy 2.0's async capabilities, implement proper CORS middleware with environment-specific configuration, and adopt cursor-based pagination for time-series data queries.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115+ | Async-first web framework | Industry standard for high-performance Python APIs with automatic OpenAPI documentation |
| SQLAlchemy 2.0 | 2.0+ | Async ORM | Mature async support with connection pooling and query optimization |
| asyncpg | 0.30+ | PostgreSQL driver | Most performant async PostgreSQL adapter with connection pooling support |
| Pydantic | 2.0+ | Data validation | Integrated with FastAPI for automatic request/response validation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Uvicorn | 0.30+ | ASGI server | Production ASGI server with async support |
| APScheduler | 3.10+ | Background jobs | For scheduled data fetching (already implemented) |
| Python 3.10+ | 3.10+ | Runtime | Required for async/await syntax and modern Python features |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLAlchemy async | Tortoise ORM | Less mature async support, fewer features |
| asyncpg | aiopg | Better performance but less active maintenance |
| Axios | Fetch API | Axios has better error handling and request cancellation |

**Installation:**
```bash
pip install fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg pydantic python-dotenv
```

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py (exists)
│   │   ├── entities.py (new)
│   │   └── sentiment.py (new)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── entity.py (new)
│   │   └── sentiment.py (new)
│   └── dependencies.py (new)
├── db/
│   ├── models.py (exists)
│   ├── session.py (exists)
│   └── base.py (exists)
├── pipeline/
│   └── (already implemented)
└── main.py (exists)
```

### Pattern 1: Async API Route with Dependency Injection
**What:** Use FastAPI's dependency injection for database sessions and implement async endpoints
**When to use:** All database-accessing API routes
**Example:**
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import datetime, timedelta

router = APIRouter(prefix="/entities", tags=["entities"])

@router.get("/", response_model=List[EntitySchema])
async def get_entities(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=1000)
):
    """Get all entities with latest sentiment scores."""
    result = await session.execute(
        select(Entity)
        .order_by(Entity.name)
        .limit(limit)
    )
    return result.scalars().all()
```

### Pattern 2: Time-Series Cursor Pagination
**What:** Use timestamp-based cursors for efficient time-series data retrieval
**When to use:** Large dataset queries where consistent performance is critical
**Example:**
```python
from typing import Optional

@router.get("/sentiment")
async def get_entity_sentiment(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    cursor: Optional[str] = Query(None, description="Timestamp for pagination"),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get time-series sentiment data with date filtering."""
    query = select(SentimentTimeseries).where(
        SentimentTimeseries.entity_id == entity_id
    )

    # Apply date range
    if start_date:
        query = query.where(SentimentTimeseries.timestamp >= start_date)
    if end_date:
        query = query.where(SentimentTimeseries.timestamp <= end_date)

    # Apply cursor pagination
    if cursor:
        cursor_time = datetime.fromisoformat(cursor)
        query = query.where(SentimentTimeseries.timestamp < cursor_time)

    query = query.order_by(
        SentimentTimeseries.timestamp.desc()
    ).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()
```

### Anti-Patterns to Avoid
- **Sync database calls in async endpoints:** Will block the event loop
- **Manual connection management:** Use FastAPI dependency injection instead
- **Large response payloads without pagination:** Always paginate large datasets
- **Ignoring error handling:** FastAPI provides automatic validation errors, but handle database errors explicitly

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client logic | Custom fetch/axios wrapper | httpx or requests | Proper error handling, timeout management, retries |
| CORS configuration | Custom middleware | FastAPI's CORSMiddleware | Built-in support for all CORS scenarios |
| API documentation | Custom docs | FastAPI automatic OpenAPI | Comprehensive, interactive docs with validation |
| Database connection management | Custom connection pooling | SQLAlchemy async engine | Connection pooling, pre-ping, proper cleanup |
| Error response formatting | Custom error handlers | FastAPI HTTPException | Consistent error formats, proper HTTP status codes |

**Key insight:** FastAPI provides a complete toolkit that eliminates the need for custom implementations of common API patterns, allowing focus on business logic rather than infrastructure.

## Common Pitfalls

### Pitfall 1: Connection Pool Exhaustion
**What goes wrong:** Too many concurrent requests exhaust the database connection pool, causing 503 errors
**Why it happens:** Default pool settings may not match expected load, or connections aren't properly closed
**How to avoid:** Monitor pool usage, set appropriate pool_size/max_overflow, ensure proper session cleanup
**Warning signs:** Slow response times under load, connection timeout errors

### Pitfall 2: N+1 Query Problem
**What goes wrong:** Multiple database queries executed for each entity (one for entities + N for sentiment data)
**Why it happens:** Not using SQLAlchemy's joined_load or relationship loading
**How to avoid:** Use `joinedload` or `selectinload` for relationship data, optimize query structure
**Warning signs:** Slow API responses under load, database showing many small queries

### Pitfall 3: CORS Misconfiguration
**What goes wrong:** CORS policy blocks frontend requests, or over-permissive in production
**Why it happens:** Using development settings (`allow_origins=["*"]`) in production
**How to avoid:** Use environment-specific configuration, restrict to specific domains in production
**Warning signs:** Browser console showing CORS errors, network requests failing

### Pitfall 4: Time-Series Query Performance
**What goes wrong:** Slow queries when retrieving large time-series datasets
**Why it happens:** Missing proper indexing or inefficient query structure
**How to avoid:** Use composite indexes, implement cursor pagination, limit date ranges
**Warning signs:** API timeouts, slow response times for time-series endpoints

## Code Examples

### Entity Endpoint with Error Handling
```python
from fastapi import HTTPException
from sqlalchemy.exc import NoResultFound

@router.get("/{entity_id}", response_model=EntityDetailSchema)
async def get_entity(
    entity_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a specific entity with latest sentiment data."""
    try:
        result = await session.execute(
            select(Entity)
            .where(Entity.id == entity_id)
        )
        entity = result.scalar_one()
        return entity
    except NoResultFound:
        raise HTTPException(
            status_code=404,
            detail=f"Entity with ID {entity_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
```

### CORS Configuration with Environment Variables
```python
# In main.py
from fastapi.middleware.cors import CORSMiddleware
import os

if os.getenv("ENVIRONMENT") == "production":
    CORS_ORIGINS = [
        "https://your-react-domain.com",
        "https://www.your-react-domain.com"
    ]
else:
    CORS_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Content-Range"],
    max_age=3600,
)
```

### Efficient Time-Series Query with Pagination
```python
from typing import Optional
from datetime import datetime

@router.get("/{entity_id}/sentiment")
async def get_sentiment_timeseries(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    cursor: Optional[str] = Query(None, description="Timestamp for pagination"),
    limit: int = Query(100, ge=1, le=1000),
    period: str = Query("daily", regex="^(hourly|daily)$")
):
    """Get time-series sentiment data with optional date filtering."""

    query = select(SentimentTimeseries).where(
        SentimentTimeseries.entity_id == entity_id,
        SentimentTimeseries.period == period
    )

    # Apply date range filters
    if start_date:
        query = query.where(SentimentTimeseries.timestamp >= start_date)
    if end_date:
        query = query.where(SentimentTimeseries.timestamp <= end_date)

    # Apply cursor pagination for consistent performance
    if cursor:
        cursor_time = datetime.fromisoformat(cursor)
        query = query.where(SentimentTimeseries.timestamp < cursor_time)

    query = query.order_by(
        SentimentTimeseries.timestamp.desc()
    ).limit(limit)

    result = await session.execute(query)
    data = result.scalars().all()

    # Generate next cursor for pagination
    next_cursor = None
    if len(data) > 0:
        next_cursor = data[-1].timestamp.isoformat()

    return {
        "data": data,
        "next_cursor": next_cursor,
        "has_more": len(data) == limit
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Offset-based pagination | Cursor-based pagination | 2024 | Consistent performance with large datasets |
| Synchronous database calls | Async/await throughout | 2022 | Better performance under load |
| Manual CORS configuration | Environment-specific middleware | 2023 | Improved security for production |
| Custom error handling | FastAPI automatic validation | 2021 | Less boilerplate, better error responses |
| Multiple database extensions | PostgreSQL with TimescaleDB | 2026 | Reduced operational complexity |

**Deprecated/outdated:**
- `sqlalchemy.create_engine` with sync drivers (use `create_async_engine`)
- Manual session management per request (use dependency injection)
- Custom JSON serialization (use Pydantic)
- Request body parsing without validation (use Pydantic models)

## Open Questions

1. **API Versioning Strategy**
   - What we know: FastAPI supports multiple approaches (URL path, headers)
   - What's unclear: Which strategy fits a sentiment tracking API best
   - Recommendation: Start with URL versioning (/v1/entities) for clarity

2. **Data Aggregation Strategy**
   - What we know: SentimentTimeseries already stores hourly/daily aggregates
   - What's unclear: Should API allow custom time ranges beyond pre-computed periods
   - Recommendation: Support pre-computed periods first, add custom aggregation later

3. **Real-time Updates**
   - What we know: APScheduler polls data periodically
   - What's unclear: Should API support WebSocket streaming for real-time updates
   - Recommendation: Implement polling-based updates first, consider WebSockets later

## Sources

### Primary (HIGH confidence)
- [FastAPI Documentation - Handling Errors](https://fastapi.tiangolo.com/tutorial/handling-errors/) - Official error handling patterns
- [FastAPI Documentation - SQL Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/) - Official async database integration
- [FastAPI Documentation - CORS Middleware](https://fastapi.tiangolo.com/tutorial/cors/) - Official CORS configuration
- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) - Current async ORM features

### Secondary (MEDIUM confidence)
- [Building High-Performance APIs with FastAPI and Async Python](https://dasroot.net/posts/2026/01/building-high-performance-apis-fastapi-async-python/) - Performance optimization patterns
- [FastAPI Best Practices: A Complete Guide](https://medium.com/@abipoongodi1211/fastapi-best-practices-a-complete-guide-for-building-production-ready-apis-bb27062d7617) - Community best practices
- [Asynchronous Pagination in FastAPI for Large Result Sets](https://medium.com/@bhagyarana80/asynchronous-pagination-in-fastapi-for-large-result-sets-62925ceb96a4) - Pagination implementation patterns

### Tertiary (LOW confidence)
- [Cursor Pagination vs Offset: Scalable Database Performance](https://www.linkedin.com/posts/gyanesh-sharma09_systemdesign_backendengineering-apidesign-activity-7414521818704928768-NbRW) - Pagination tradeoffs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are well-established with clear official documentation
- Architecture: HIGH - Async patterns and dependency injection are standard FastAPI practices
- Pitfalls: HIGH - Common issues are well-documented in official documentation and community guides

**Research date:** 2026-02-05
**Valid until:** 2026-03-05 (30 days for stable web framework ecosystem)