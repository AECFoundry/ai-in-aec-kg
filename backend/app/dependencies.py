from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase
from openai import AsyncOpenAI

from app.config import get_settings

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_neo4j_driver: AsyncDriver | None = None
_openai_client: AsyncOpenAI | None = None


# ---------------------------------------------------------------------------
# Neo4j
# ---------------------------------------------------------------------------

async def init_neo4j_driver() -> AsyncDriver:
    """Create and return the Neo4j async driver (call once at startup)."""
    global _neo4j_driver
    settings = get_settings()
    _neo4j_driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    return _neo4j_driver


async def close_neo4j_driver() -> None:
    """Close the Neo4j driver (call at shutdown)."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        await _neo4j_driver.close()
        _neo4j_driver = None


async def get_neo4j_driver() -> AsyncDriver:
    """FastAPI dependency that yields the Neo4j driver."""
    if _neo4j_driver is None:
        raise RuntimeError("Neo4j driver not initialised")
    return _neo4j_driver


# ---------------------------------------------------------------------------
# OpenAI / OpenRouter
# ---------------------------------------------------------------------------

def init_openai_client() -> AsyncOpenAI:
    """Create and return the AsyncOpenAI client pointed at OpenRouter."""
    global _openai_client
    settings = get_settings()
    _openai_client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )
    return _openai_client


def get_openai_client() -> AsyncOpenAI:
    """FastAPI dependency that returns the OpenAI/OpenRouter client."""
    if _openai_client is None:
        raise RuntimeError("OpenAI client not initialised")
    return _openai_client
