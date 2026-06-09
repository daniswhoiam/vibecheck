"""Health-check test for the API service.

No lifespan/pool is started, so liveness never depends on a database.
"""

from api.main import app
from httpx import ASGITransport, AsyncClient


async def test_health_returns_ok() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
