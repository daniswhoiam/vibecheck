"""Versioned dashboard read endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from lib_db import queries
from psycopg import AsyncConnection

from api.dependencies import get_conn
from api.models import Tool

router = APIRouter(prefix="/api/v1")


@router.get("/tools", response_model=list[Tool])
async def list_tools(
    conn: AsyncConnection[Any] = Depends(get_conn),
) -> list[Tool]:
    rows = await queries.list_tools(conn)
    return [Tool(slug=r.slug, display_name=r.display_name, aliases=r.aliases) for r in rows]
