"""LLM provider utilities for the pipeline.

Supports OpenRouter (OPENROUTER_API_KEY) and direct OpenAI (OPENAI_API_KEY).
If both are set, OpenRouter takes precedence.
"""

from __future__ import annotations

import os


def get_api_key() -> str:
    """Return the active LLM API key, preferring OpenRouter."""
    key = os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError(
            "No LLM API key found. "
            "Set OPENROUTER_API_KEY or OPENAI_API_KEY in your .env file."
        )
    return key


def get_base_url() -> str | None:
    """Return the base URL for the LLM API, or None for default OpenAI."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return "https://openrouter.ai/api/v1"
    return None


def use_openrouter() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def resolve_model(model: str) -> str:
    """Resolve an OpenRouter-style model name for the active provider.

    OpenRouter uses prefixed names (openai/gpt-4.1, google/gemini-2.5-flash).
    Direct OpenAI uses bare names (gpt-4.1, text-embedding-3-large).
    Google models fall back to gpt-4.1-mini on direct OpenAI.
    """
    if use_openrouter():
        return model
    if model.startswith("openai/"):
        return model.removeprefix("openai/")
    if model.startswith("google/"):
        return "gpt-4.1-mini"
    return model
