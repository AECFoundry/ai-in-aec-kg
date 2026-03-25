from __future__ import annotations

from openai import AsyncOpenAI

from app.config import get_settings


def get_openrouter_client() -> AsyncOpenAI:
    """Factory for an AsyncOpenAI client pointed at OpenRouter."""
    settings = get_settings()
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )
