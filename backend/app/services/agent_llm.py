"""LLM factory for the LangGraph agent."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import get_settings


def get_agent_llm() -> ChatOpenAI:
    """Create a ChatOpenAI instance using the configured LLM provider."""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.resolve_model(settings.AGENT_MODEL),
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        temperature=0.2,
        max_tokens=4000,
        streaming=True,
    )
