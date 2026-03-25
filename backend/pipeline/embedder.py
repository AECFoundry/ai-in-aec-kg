"""Generate embeddings for all graph nodes via OpenRouter."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from openai import AsyncOpenAI

from pipeline.extractor import Entity

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "openai/text-embedding-3-large"
BATCH_SIZE = 100


def _build_text_for_entity(entity: Entity) -> str:
    """Build the text to embed for a given entity."""
    desc = entity.description or ""
    return f"{entity.name}. {desc}".strip()


def _build_text_for_session(session_dict: dict) -> str:
    """Build the text to embed for a session."""
    title = session_dict.get("title", "")
    summary = session_dict.get("summary_text", "")
    return f"{title}. {summary[:500]}".strip()


async def _embed_batch(
    client: AsyncOpenAI,
    texts: list[str],
    *,
    model: str = EMBEDDING_MODEL,
) -> list[list[float]]:
    """Embed a batch of texts."""
    response = await client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


async def embed_all_nodes(
    entities: list[Entity],
    sessions_data: list[dict],
    client: AsyncOpenAI,
    *,
    model: str = EMBEDDING_MODEL,
) -> dict[str, list[float]]:
    """Generate embeddings for all graph nodes.

    Returns a dict mapping entity/session ID to its embedding vector.
    """
    texts_by_id: dict[str, str] = {}

    # Session nodes
    for session_dict in sessions_data:
        sid = f"session_{session_dict['session_number']}"
        texts_by_id[sid] = _build_text_for_session(session_dict)

    # Entity nodes (excluding sessions, which we already handled)
    for entity in entities:
        if entity.type == "Session":
            continue
        texts_by_id[entity.id] = _build_text_for_entity(entity)

    all_ids = list(texts_by_id.keys())
    all_texts = list(texts_by_id.values())
    embeddings: dict[str, list[float]] = {}

    total = len(all_texts)
    logger.info("Embedding %d nodes in batches of %d", total, BATCH_SIZE)

    for i in range(0, total, BATCH_SIZE):
        batch_texts = all_texts[i : i + BATCH_SIZE]
        batch_ids = all_ids[i : i + BATCH_SIZE]

        try:
            batch_embeddings = await _embed_batch(client, batch_texts, model=model)
            for j, emb in enumerate(batch_embeddings):
                embeddings[batch_ids[j]] = emb
            logger.info(
                "Embedded batch %d-%d of %d",
                i + 1,
                min(i + BATCH_SIZE, total),
                total,
            )
        except Exception as exc:
            logger.error("Embedding batch %d failed: %s", i // BATCH_SIZE + 1, exc)
            # Continue with remaining batches
            continue

    logger.info("Generated %d embeddings (dimension=%d)", len(embeddings), 3072)
    return embeddings


def run_embed(
    entities: list[Entity],
    sessions_data: list[dict],
    api_key: str,
) -> dict[str, list[float]]:
    """Synchronous convenience wrapper for embed_all_nodes."""
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    return asyncio.run(embed_all_nodes(entities, sessions_data, client))


def embeddings_to_serializable(embeddings: dict[str, list[float]]) -> dict[str, Any]:
    """Convert embeddings dict to JSON-serializable format (truncate for cache)."""
    # Store full embeddings — they're needed for loading
    return embeddings


if __name__ == "__main__":
    import json
    import os
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    logging.basicConfig(level=logging.INFO)

    cache_dir = Path(__file__).resolve().parents[1] / "data" / "pipeline_cache"
    enrich_path = cache_dir / "enrich_output.json"
    parse_path = cache_dir / "parse_output.json"

    if not enrich_path.exists():
        print(f"No enrich output at {enrich_path}. Run enrich stage first.")
        raise SystemExit(1)
    if not parse_path.exists():
        print(f"No parse output at {parse_path}. Run parse stage first.")
        raise SystemExit(1)

    from pipeline.extractor import Entity, ExtractionResult

    enrich_data = json.loads(enrich_path.read_text(encoding="utf-8"))
    sessions_data = json.loads(parse_path.read_text(encoding="utf-8"))
    extraction = ExtractionResult.from_dict(enrich_data)

    embeddings = run_embed(
        extraction.entities,
        sessions_data,
        os.environ["OPENROUTER_API_KEY"],
    )
    print(f"Generated {len(embeddings)} embeddings")

    # Save embeddings (can be large)
    out = cache_dir / "embed_output.json"
    out.write_text(json.dumps(embeddings, indent=None, ensure_ascii=False))
    print(f"Wrote {out}")
