"""Unit tests for Production Server, Web Chat Front-End, and Healthcheck Probes."""
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


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_chat_front_end():
    # Browser request to root returns HTML Chat UI
    response = client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Altostrat HR & IT Policy Assistant" in response.text
    assert "ADK Dev UI" in response.text


def test_root_json_metadata():
    # Programmatic JSON request returns service info
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert "health_check" in data
    assert data["health_check"] == "/healthz"
    assert "chat_endpoint" in data
    assert data["chat_endpoint"] == "/api/v1/chat"


def test_chat_ui_endpoint():
    # Direct /chat route returns HTML Chat UI
    response = client.get("/chat")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Altostrat HR & IT Policy Assistant" in response.text


def test_dev_ui_endpoint():
    # ADK Dev UI is mounted and accessible
    response = client.get("/dev-ui/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_chat_endpoint_validation():
    # Empty query should return 400 Bad Request
    response = client.post("/api/v1/chat", json={"query": "   "})
    assert response.status_code == 400
