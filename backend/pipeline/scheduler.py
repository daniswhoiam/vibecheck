"""APScheduler integration for automated data pipeline jobs.

Manages scheduled job execution with health monitoring and audit logging.
All four Phase 6 data collection jobs are registered in setup_jobs().
Each collection job chains into score_sentiment and aggregate_sentiment —
one log entry per source per pipeline cycle.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from db.models import SchedulerExecutionLog

from pipeline.jobs.collect_hackernews import run_collect_hackernews
from pipeline.jobs.collect_reddit import run_collect_reddit
from pipeline.jobs.collect_discourse import run_collect_discourse
from pipeline.jobs.collect_devto import run_collect_devto
from pipeline.jobs.score_sentiment import run_score_sentiment
from pipeline.jobs.aggregate_sentiment import run_aggregate_sentiment
from pipeline.jobs.extract_aspects import run_extract_aspects

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


async def wrapped_pipeline_execution(
    job_name: str,
    collect_func: Callable[[AsyncSession], dict[str, Any]],
    db_session: AsyncSession
) -> None:
    """Execute collect → score → aggregate → extract_aspects pipeline with audit logging.

    Chains four steps in sequence:
    1. Collect: fetch new posts from the source
    2. Score: classify any unscored posts with GliClass
    3. Aggregate: recompute today's sentiment rollup for all entities
    4. Extract aspects: run LLM aspect extraction for low-confidence posts

    Each step is logged separately. Collect failures are logged but do not
    prevent scoring/aggregation/aspect-extraction — previously unscored posts
    from earlier runs should still be processed.

    Args:
        job_name: Source identifier (e.g., 'collect_hackernews')
        collect_func: The source-specific collection job function
        db_session: Shared database session for all three pipeline steps
    """
    execution_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    pipeline_stats: dict[str, Any] = {}

    logger.info("Pipeline execution started: %s (id=%s)", job_name, execution_id)

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

    errors = []

    # Step 1: Collect
    try:
        collect_stats = await collect_func(db_session)
        pipeline_stats["collection"] = collect_stats
        logger.info("%s: collected %s posts", job_name, collect_stats.get("collected", "?"))
    except Exception as exc:
        logger.error("%s: collection failed: %s", job_name, exc, exc_info=True)
        pipeline_stats["collection"] = {"error": str(exc)}
        errors.append(f"collection: {exc}")

    # Step 2: Score (always attempt, even if collection failed)
    try:
        score_stats = await run_score_sentiment(db_session)
        pipeline_stats["sentiment"] = score_stats
        logger.info("%s: scored %s posts", job_name, score_stats.get("scored", "?"))
    except Exception as exc:
        logger.error("%s: scoring failed: %s", job_name, exc, exc_info=True)
        pipeline_stats["sentiment"] = {"error": str(exc)}
        errors.append(f"scoring: {exc}")

    # Step 3: Aggregate (always attempt, even if scoring failed)
    try:
        agg_stats = await run_aggregate_sentiment(db_session)
        pipeline_stats["aggregation"] = agg_stats
        logger.info("%s: updated %s rollups", job_name, agg_stats.get("rollups_updated", "?"))
    except Exception as exc:
        logger.error("%s: aggregation failed: %s", job_name, exc, exc_info=True)
        pipeline_stats["aggregation"] = {"error": str(exc)}
        errors.append(f"aggregation: {exc}")

    # Step 4: Extract aspects (always attempt — processes all low-confidence posts globally,
    # not just ones collected in this run; each collect source triggers this but the job
    # is idempotent so only unprocessed posts are touched)
    try:
        aspect_stats = await run_extract_aspects(db_session)
        pipeline_stats["aspect_extraction"] = aspect_stats
        logger.info(
            "%s: extracted aspects for %s posts",
            job_name, aspect_stats.get("extracted", "?")
        )
    except Exception as exc:
        logger.error("%s: aspect extraction failed: %s", job_name, exc, exc_info=True)
        pipeline_stats["aspect_extraction"] = {"error": str(exc)}
        errors.append(f"aspect_extraction: {exc}")

    # Finalize log entry
    completed_at = datetime.now(timezone.utc)
    duration = (completed_at - started_at).total_seconds()

    log_entry.status = "failed" if errors else "success"
    log_entry.completed_at = completed_at
    log_entry.duration_seconds = duration
    log_entry.metadata_json = pipeline_stats
    if errors:
        log_entry.error_message = "; ".join(errors)

    await db_session.commit()

    # Update health tracking (track on success only)
    if not errors:
        job_last_run[job_name] = completed_at

    logger.info(
        "Pipeline execution complete: %s (id=%s, duration=%.2fs, status=%s)",
        job_name, execution_id, duration, log_entry.status,
    )


def setup_jobs() -> None:
    """Register all data collection jobs with APScheduler.

    Four collection sources, each running every 6 hours.
    Staggered 30 minutes apart to smooth resource usage:
      - HN:        runs at startup time (no delay)
      - Reddit:    runs 30 minutes after startup
      - Discourse: runs 60 minutes after startup
      - Dev.to:    runs 90 minutes after startup

    Uses replace_existing=True + explicit id= to prevent duplicate job
    accumulation on app restarts / hot reloads.

    Each job is wrapped in wrapped_job_execution() which:
    - Creates its own AsyncSession
    - Logs to SchedulerExecutionLog
    - Captures exceptions without crashing the scheduler
    """
    from apscheduler.triggers.interval import IntervalTrigger

    now = datetime.now(timezone.utc)

    def _make_scheduled_job(job_name: str, job_func):
        """Create APScheduler-compatible wrapper for collect→score→aggregate pipeline."""
        async def _job():
            async with AsyncSessionLocal() as db_session:
                await wrapped_pipeline_execution(job_name, job_func, db_session)
        return _job

    job_definitions = [
        ("collect_hackernews", run_collect_hackernews, 0),    # No delay
        ("collect_reddit",     run_collect_reddit,     30),   # +30 min
        ("collect_discourse",  run_collect_discourse,  60),   # +60 min
        ("collect_devto",      run_collect_devto,      90),   # +90 min
    ]

    for job_name, job_func, delay_minutes in job_definitions:
        scheduler.add_job(
            _make_scheduled_job(job_name, job_func),
            trigger=IntervalTrigger(hours=6),
            next_run_time=now + timedelta(minutes=delay_minutes),
            id=job_name,
            replace_existing=True,
            name=job_name,
        )
        logger.info(
            "Registered job '%s' — interval=6h, first_run=%s",
            job_name,
            (now + timedelta(minutes=delay_minutes)).isoformat(),
        )


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
    job_configs: dict[str, dict] = {
        "collect_hackernews": {"interval_minutes": 360},
        "collect_reddit":     {"interval_minutes": 360},
        "collect_discourse":  {"interval_minutes": 360},
        "collect_devto":      {"interval_minutes": 360},
    }

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
