"""APScheduler integration for automated data pipeline jobs.

Manages scheduled job execution with health monitoring and audit logging.
Job registrations placeholder — new source jobs will be added in Phase 6.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models import SchedulerExecutionLog

logger = logging.getLogger(__name__)

# Module-level scheduler instance
scheduler = AsyncIOScheduler(timezone='UTC')

# Track last successful run time for health checks
job_last_run: dict[str, datetime] = {}


async def wrapped_job_execution(
    job_name: str,
    job_func: Callable[[AsyncSession], dict[str, Any]],
    db_session: AsyncSession
) -> None:
    """Execute job with audit logging and error handling.

    Wraps job execution to:
    - Generate unique execution_id for tracing
    - Log start/completion to SchedulerExecutionLog table
    - Capture errors without crashing scheduler
    - Track last successful run time for health monitoring
    - Store job execution metadata (stats returned by job)

    Args:
        job_name: Identifier for the job (e.g., 'collect_hackernews')
        job_func: Async function that executes the job logic
        db_session: Database session for logging and job execution
    """
    execution_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    logger.info("Job execution started: %s (id=%s)", job_name, execution_id)

    # Create execution log entry
    log_entry = SchedulerExecutionLog(
        execution_id=execution_id,
        job_name=job_name,
        status="running",
        started_at=started_at,
        completed_at=None,
        duration_seconds=None,
        error_message=None,
        metadata_json=None,
    )
    db_session.add(log_entry)
    await db_session.commit()

    try:
        # Execute job
        job_stats = await job_func(db_session)

        # Job completed successfully
        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        log_entry.status = "success"
        log_entry.completed_at = completed_at
        log_entry.duration_seconds = duration
        log_entry.metadata_json = job_stats

        await db_session.commit()

        # Update health tracking
        job_last_run[job_name] = completed_at

        logger.info(
            "Job execution completed: %s (id=%s, duration=%.2fs)",
            job_name, execution_id, duration,
        )

    except Exception as exc:
        # Job failed - log error but don't crash scheduler
        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        log_entry.status = "failed"
        log_entry.completed_at = completed_at
        log_entry.duration_seconds = duration
        log_entry.error_message = str(exc)

        await db_session.commit()

        logger.error(
            "Job execution failed: %s (id=%s, error=%s)",
            job_name, execution_id, str(exc),
            exc_info=True,
        )


def setup_jobs() -> None:
    """Register scheduled jobs with APScheduler.

    Placeholder — job registrations removed in Phase 5 cleanup.
    New data source collection jobs will be added in Phase 6.
    """
    pass


async def get_job_health() -> dict[str, Any]:
    """Get health status for all scheduled jobs.

    Returns job last run times and alerts if jobs are overdue.
    A job is considered overdue if it hasn't run in 2x its scheduled interval.

    Returns:
        Dict with structure:
        {
            "healthy": bool,
            "jobs": { ... }
        }
    """
    now = datetime.now(timezone.utc)
    # Job configs will be populated when Phase 6 adds real jobs
    job_configs: dict[str, dict] = {}

    jobs_status = {}
    all_healthy = True

    for job_name, config in job_configs.items():
        last_run = job_last_run.get(job_name)
        interval_minutes = config["interval_minutes"]

        if last_run is None:
            jobs_status[job_name] = {
                "last_run": None,
                "interval_minutes": interval_minutes,
                "overdue": False,
                "minutes_since_last_run": None,
            }
        else:
            time_since_run = (now - last_run).total_seconds() / 60
            overdue = time_since_run > (interval_minutes * 2)

            jobs_status[job_name] = {
                "last_run": last_run.isoformat(),
                "interval_minutes": interval_minutes,
                "overdue": overdue,
                "minutes_since_last_run": round(time_since_run, 2),
            }

            if overdue:
                all_healthy = False

    return {
        "healthy": all_healthy,
        "jobs": jobs_status,
    }
