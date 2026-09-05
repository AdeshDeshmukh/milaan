"""Unit tests for FastAPI UI endpoints."""

from fastapi.testclient import TestClient
from milaan.ui.server import app

client = TestClient(app)


def test_ui_index():
    response = client.get("/")
    assert response.status_code == 200


def test_api_summary():
    response = client.get("/api/summary")
    assert response.status_code == 200
    data = response.json()
    assert "overall_match_rate_pct" in data
    assert "audit_verified" in data


def test_api_matches():
    response = client.get("/api/matches")
    assert response.status_code == 200
    data = response.json()
    assert "matches" in data


def test_api_exceptions():
    response = client.get("/api/exceptions")
    assert response.status_code == 200
    data = response.json()
    assert "exceptions" in data


def test_api_proposals():
    response = client.get("/api/proposals")
    assert response.status_code == 200
    data = response.json()
    assert "proposals" in data


def test_api_audit():
    response = client.get("/api/audit")
    assert response.status_code == 200
    data = response.json()
    assert "verified" in data
    assert data["verified"] is True
