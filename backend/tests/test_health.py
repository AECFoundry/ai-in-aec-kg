"""Tests for the /api/health endpoint."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_neo4j_driver
from app.main import app


@pytest.fixture
def mock_neo4j_driver():
    """Create a mock Neo4j async driver."""
    driver = AsyncMock()
    session = AsyncMock()
    result = AsyncMock()
    record = {"n": 1}

    result.single = AsyncMock(return_value=record)
    session.run = AsyncMock(return_value=result)

    # Make session usable as async context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    driver.session = lambda: session
    return driver


@pytest.fixture
def override_driver(mock_neo4j_driver):
    """Override the Neo4j driver dependency."""
    async def _override():
        return mock_neo4j_driver

    app.dependency_overrides[get_neo4j_driver] = _override
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_returns_200(override_driver):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["neo4j"] == "connected"


@pytest.mark.asyncio
async def test_health_degraded_when_neo4j_down():
    """When Neo4j is unreachable the endpoint should report degraded."""
    driver = AsyncMock()
    session = AsyncMock()
    session.run = AsyncMock(side_effect=Exception("Connection refused"))
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    driver.session = lambda: session

    async def _override():
        return driver

    app.dependency_overrides[get_neo4j_driver] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["neo4j"] == "unreachable"
    finally:
        app.dependency_overrides.clear()
