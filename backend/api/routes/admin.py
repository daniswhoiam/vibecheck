"""Admin routes for manual pipeline triggering.

Pipeline trigger endpoints will be re-added in Phase 6 when new data sources are implemented.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
