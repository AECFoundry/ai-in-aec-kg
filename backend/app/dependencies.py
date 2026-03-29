from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase
from openai import AsyncOpenAI

from app.config import get_settings

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_neo4j_driver: AsyncDriver | None = None
_openai_client: AsyncOpenAI | None = None
_tts_client: AsyncOpenAI | None = None


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
    """Create and return the AsyncOpenAI client (OpenRouter or direct OpenAI)."""
    global _openai_client
    settings = get_settings()
    _openai_client = AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
    return _openai_client


def get_openai_client() -> AsyncOpenAI:
    """FastAPI dependency that returns the OpenAI/OpenRouter client."""
    if _openai_client is None:
        raise RuntimeError("OpenAI client not initialised")
    return _openai_client


# ---------------------------------------------------------------------------
# TTS (direct OpenAI — never OpenRouter)
# ---------------------------------------------------------------------------

def init_tts_client() -> AsyncOpenAI | None:
    """Create a direct OpenAI client for TTS. Returns None if no OPENAI_API_KEY."""
    global _tts_client
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return None
    _tts_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _tts_client


def get_tts_client() -> AsyncOpenAI | None:
    """Return the TTS client, or None if TTS is not configured."""
    return _tts_client
