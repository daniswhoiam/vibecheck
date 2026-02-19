"""Health check endpoint for verifying API and database connectivity.

Returns database connection status for monitoring and readiness checks.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db.session import get_session
from pipeline.scheduler import get_job_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """Verify API and database connectivity.

    Tests:
        - FastAPI application is running
        - Database session dependency injection works
        - PostgreSQL connection is live and responsive
        - Async query execution succeeds

    Returns:
        dict: Health status with database connectivity state

    Examples:
        Healthy: {"status": "healthy", "database": "connected"}
        Unhealthy: {"status": "unhealthy", "database": "disconnected", "error": "..."}
    """
    try:
        # Execute simple query to verify database connectivity
        result = await session.execute(text("SELECT 1"))
        result.scalar_one()

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


@router.get("/health/scheduler")
async def scheduler_health_check(response: Response):
    """Verify scheduler health and job execution status.

    Checks:
        - All scheduled jobs (poll_news, poll_stories)
        - Last run time for each job
        - Whether any jobs are overdue (>2x their interval)

    Returns:
        dict: Scheduler health status with per-job details
        - 200 OK if all jobs healthy
        - 503 Service Unavailable if any job overdue

    Examples:
        Healthy: {"healthy": true, "jobs": {"poll_news": {...}}}
        Unhealthy: {"healthy": false, "jobs": {"poll_news": {"overdue": true}}}
    """
    job_health = await get_job_health()

    # Set 503 status if scheduler unhealthy
    if not job_health["healthy"]:
        response.status_code = 503

    return job_health
