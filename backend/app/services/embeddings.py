from __future__ import annotations

from openai import AsyncOpenAI


async def embed_texts(texts: list[str], client: AsyncOpenAI) -> list[list[float]]:
    """Generate embeddings for a batch of texts via OpenRouter."""
    response = await client.embeddings.create(
        model="openai/text-embedding-3-large",
        input=texts,
    )
    return [item.embedding for item in response.data]


async def embed_text(text: str, client: AsyncOpenAI) -> list[float]:
    """Generate an embedding for a single text string."""
    result = await embed_texts([text], client)
    return result[0]
