"""Unit tests for Production Server and Healthcheck Probes."""
import pytest
from agent.server import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "hr_policy_agent"
    assert data["version"] == "1.0.0"


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "health_check" in data
    assert data["health_check"] == "/healthz"
    assert "chat_endpoint" in data
    assert data["chat_endpoint"] == "/api/v1/chat"


def test_chat_endpoint_validation():
    # Empty query should return 400 Bad Request
    response = client.post("/api/v1/chat", json={"query": "   "})
    assert response.status_code == 400
