from __future__ import annotations

from app.config import get_settings
from openai import AsyncOpenAI

EMBEDDING_MODEL = "openai/text-embedding-3-large"


async def embed_texts(texts: list[str], client: AsyncOpenAI) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    settings = get_settings()
    response = await client.embeddings.create(
        model=settings.resolve_model(EMBEDDING_MODEL),
        input=texts,
    )
    return [item.embedding for item in response.data]


async def embed_text(text: str, client: AsyncOpenAI) -> list[float]:
    """Generate an embedding for a single text string."""
    result = await embed_texts([text], client)
    return result[0]
