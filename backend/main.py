"""FastAPI application with lifespan management for database initialization.

Provides REST API for VibeCheck sentiment tracking system.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.session import engine
from db.base import Base
from api.routes import health, entities, sentiment, admin
from pipeline.scheduler import scheduler, setup_jobs
from scripts.seed_entities import seed_entities


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events.

    Startup:
        - Run Alembic migrations to upgrade database schema
        - Register scheduled jobs (news every 15 min, stories every 60 min)
        - Start APScheduler for automated polling

    Shutdown:
        - Shutdown scheduler gracefully (wait for running jobs)
        - Dispose of database engine and connection pool
        - Ensures clean resource cleanup
    """
    # Startup
    print("Starting up application...")
    # NOTE: Database migrations are handled by docker-entrypoint.sh (alembic upgrade head)
    # before the FastAPI server starts. No need to run them here.

    # Setup and start scheduler
    setup_jobs()
    job_count = len(scheduler.get_jobs())
    print(f"Registered {job_count} scheduled jobs")
    scheduler.start()
    print("APScheduler started")

    yield

    # Shutdown
    print("Shutting down application...")
    scheduler.shutdown(wait=True)
    print("APScheduler shutdown complete")
    await engine.dispose()


# Create FastAPI application instance
app = FastAPI(
    title="VibeCheck API",
    description="Sentiment tracking for AI entities",
    version="0.1.0",
    lifespan=lifespan
)

# CORS configured via ENVIRONMENT and CORS_ORIGINS environment variables
#   Development: Allows all origins or configured origins
#   Production: Restrict to specific frontend domains

# Get environment and CORS origins from environment
environment = os.getenv("ENVIRONMENT", "development")

# Parse CORS origins from comma-separated string
cors_origins_str = os.getenv("CORS_ORIGINS", "*")
if cors_origins_str == "*":
    cors_origins = ["*"]
else:
    cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]

# Log CORS configuration in development
if environment == "development":
    print(f"CORS allowed origins: {cors_origins}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Range"],
    max_age=3600,  # Cache preflight responses for 1 hour
)

# Include routers
app.include_router(health.router)
app.include_router(entities.router)
app.include_router(sentiment.router)
app.include_router(admin.router)
