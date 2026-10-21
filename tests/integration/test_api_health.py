from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.api.main import create_app
from src.infrastructure.config import settings
from src.infrastructure.db.session import get_db


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_check_success(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["version"] == settings.API_VERSION
    assert "DATABASE_URL" not in str(data)
    assert "key" not in str(data).lower()


def test_health_check_database_failure(client: TestClient):
    mock_session = MagicMock()
    mock_session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("Database offline simulation"))

    def broken_db():
        yield mock_session

    app = client.app
    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
    finally:
        app.dependency_overrides.clear()


def test_cors_headers_allowed_origin(client: TestClient):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_headers_disallowed_origin(client: TestClient):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://malicious-site.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None
