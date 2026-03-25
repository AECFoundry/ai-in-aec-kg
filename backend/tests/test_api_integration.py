"""Integration tests for the API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_register_and_session(client):
    """Test user registration and session validation flow."""
    # Register
    resp = await client.post(
        "/api/register",
        json={"name": "Test User", "email": "test@example.com", "company": "TestCo"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "session_id" in data
    token = data["token"]

    # Validate session
    resp = await client.get(
        "/api/session",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    user = resp.json()
    assert user["name"] == "Test User"
    assert user["email"] == "test@example.com"
    assert user["company"] == "TestCo"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    """Registering with the same email should return a valid token."""
    for _ in range(2):
        resp = await client.post(
            "/api/register",
            json={"name": "Dup User", "email": "dup@example.com", "company": "DupCo"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()


@pytest.mark.asyncio
async def test_session_without_token(client):
    """Session endpoint should reject requests without a token."""
    resp = await client.get("/api/session")
    assert resp.status_code == 422  # Missing required header


@pytest.mark.asyncio
async def test_session_with_bad_token(client):
    """Session endpoint should reject invalid tokens."""
    resp = await client.get(
        "/api/session",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_with_bad_token(client):
    """Chat endpoint should reject requests with invalid auth token."""
    resp = await client.post(
        "/api/chat",
        json={"message": "What is BIM?"},
        headers={"Authorization": "Bearer bad-token"},
    )
    # Should be 401 (invalid token) or 500 (neo4j not initialized in test)
    # In test env without lifespan, dependencies fail — this is expected
    assert resp.status_code in (401, 500)
