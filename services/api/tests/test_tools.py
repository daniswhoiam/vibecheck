"""Integration tests for GET /api/v1/tools."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_tools_returns_seeded_tool(client: AsyncClient, seeded) -> None:
    response = await client.get("/api/v1/tools")
    assert response.status_code == 200
    tools = response.json()
    match = [t for t in tools if t["slug"] == seeded.slug]
    assert len(match) == 1
    tool = match[0]
    assert set(tool) == {"slug", "display_name", "aliases"}  # no id/created_at
    assert tool["display_name"] == "Sentiment Test Tool"
    assert tool["aliases"] == []
