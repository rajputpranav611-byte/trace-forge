import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_service_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "traceforge-backend"
    assert "environment" in data


def test_database_health():
    response = client.get("/api/v1/health/db")
    # Should be 200 since traceforge-db is running on port 6379
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["details"]["connected"] is True
    assert data["details"]["query_response"] == "ok"
    assert data["details"]["graph"] == "traceforge"
