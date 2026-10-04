"""Tests for FastAPI Web Server endpoints."""
import pytest
from starlette.testclient import TestClient

from src.server import app


@pytest.fixture
def client():
    return TestClient(app)

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Panjab University" in response.text

def test_stats_endpoint(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "vector_count" in data
    assert data["vector_count"] >= 600
    assert "processed_documents" in data

def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
