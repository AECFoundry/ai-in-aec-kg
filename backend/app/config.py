from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env at the repo root."""

    # LLM provider — set one or both. If OPENROUTER_API_KEY is set, OpenRouter
    # is used (supports openai/* and google/* models). Otherwise falls back to
    # direct OpenAI API via OPENAI_API_KEY.
    OPENROUTER_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    AGENT_MODEL: str = "openai/gpt-4.1"
    TTS_MODEL: str = "tts-1"
    TTS_VOICE: str = "nova"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    APP_URL: str = "http://localhost:5173"

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def has_tts(self) -> bool:
        """TTS always requires a direct OpenAI key, regardless of LLM provider."""
        return bool(self.OPENAI_API_KEY)

    @property
    def use_openrouter(self) -> bool:
        return bool(self.OPENROUTER_API_KEY)

    @property
    def llm_api_key(self) -> str:
        key = self.OPENROUTER_API_KEY or self.OPENAI_API_KEY
        if not key:
            raise ValueError(
                "No LLM API key configured. "
                "Set OPENROUTER_API_KEY or OPENAI_API_KEY in your .env file."
            )
        return key

    @property
    def llm_base_url(self) -> str | None:
        """Return OpenRouter base URL, or None for default OpenAI."""
        if self.use_openrouter:
            return "https://openrouter.ai/api/v1"
        return None

    def resolve_model(self, model: str) -> str:
        """Resolve an OpenRouter-style model name for the active provider.

        OpenRouter uses prefixed names (openai/gpt-4.1, google/gemini-2.5-flash).
        Direct OpenAI uses bare names (gpt-4.1, text-embedding-3-large).
        Google models are unavailable on direct OpenAI and fall back to gpt-4.1-mini.
        """
        if self.use_openrouter:
            return model
        if model.startswith("openai/"):
            return model.removeprefix("openai/")
        if model.startswith("google/"):
            return "gpt-4.1-mini"
        return model


@lru_cache
def get_settings() -> Settings:
    return Settings()
