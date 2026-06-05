"""Health-check tests for the API service.

Uses a non-context-managed TestClient so the app lifespan (which opens the
DB pool) does NOT run — liveness must not depend on a reachable database.
"""

from api.main import app
from fastapi.testclient import TestClient


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
