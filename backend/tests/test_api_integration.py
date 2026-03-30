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
async def test_health(client):
    """Health endpoint should respond."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_voice_capabilities(client):
    """Voice capabilities endpoint should respond."""
    resp = await client.get("/api/voice/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert "tts_available" in data
