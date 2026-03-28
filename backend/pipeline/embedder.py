"""Generate embeddings for all graph nodes via OpenRouter, including transcript chunks."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from typing import Any

from openai import AsyncOpenAI

from pipeline.extractor import Entity

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "openai/text-embedding-3-large"
BATCH_SIZE = 100

# Chunking parameters
CHUNK_TARGET_WORDS = 400
CHUNK_OVERLAP_WORDS = 50


@dataclass
class TranscriptChunk:
    """A chunk of a presentation transcript for granular embedding."""
    id: str  # chunk_{presentation_id}_{index}
    presentation_id: str
    session_id: str
    content: str
    chunk_index: int
    total_chunks: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> TranscriptChunk:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _chunk_text(text: str, target_words: int = CHUNK_TARGET_WORDS, overlap_words: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """Split text into overlapping chunks at paragraph or sentence boundaries."""
    if not text or not text.strip():
        return []

    words = text.split()
    if len(words) <= target_words:
        return [text.strip()]

    # Split into paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks: list[str] = []
    current_paras: list[str] = []
    current_word_count = 0

    for para in paragraphs:
        para_words = len(para.split())

        if current_word_count + para_words > target_words and current_paras:
            # Emit current chunk
            chunks.append("\n\n".join(current_paras))

            # Overlap: keep last paragraph(s) that fit in overlap budget
            overlap_paras: list[str] = []
            overlap_count = 0
            for p in reversed(current_paras):
                p_words = len(p.split())
                if overlap_count + p_words > overlap_words:
                    break
                overlap_paras.insert(0, p)
                overlap_count += p_words

            current_paras = overlap_paras
            current_word_count = overlap_count

        current_paras.append(para)
        current_word_count += para_words

    # Emit final chunk
    if current_paras:
        chunks.append("\n\n".join(current_paras))

    return chunks


def build_transcript_chunks(presentations_data: list[dict]) -> list[TranscriptChunk]:
    """Chunk all presentation transcripts into TranscriptChunk objects."""
    all_chunks: list[TranscriptChunk] = []

    for pres in presentations_data:
        pres_id = pres.get("id", "")
        session_id = pres.get("session_id", "")
        transcript = pres.get("transcript", "")
        if not transcript or len(transcript.strip()) < 100:
            continue

        text_chunks = _chunk_text(transcript)
        total = len(text_chunks)

        for i, chunk_text in enumerate(text_chunks):
            chunk = TranscriptChunk(
                id=f"chunk_{pres_id}_{i}",
                presentation_id=pres_id,
                session_id=session_id,
                content=chunk_text,
                chunk_index=i,
                total_chunks=total,
            )
            all_chunks.append(chunk)

    logger.info(
        "Created %d transcript chunks from %d presentations",
        len(all_chunks),
        len(presentations_data),
    )
    return all_chunks


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
    from pipeline.llm_utils import resolve_model

    response = await client.embeddings.create(model=resolve_model(model), input=texts)
    return [item.embedding for item in response.data]


async def embed_all_nodes(
    entities: list[Entity],
    sessions_data: list[dict],
    client: AsyncOpenAI,
    *,
    model: str = EMBEDDING_MODEL,
    presentations_data: list[dict] | None = None,
    transcript_chunks: list[TranscriptChunk] | None = None,
) -> dict[str, list[float]]:
    """Generate embeddings for all graph nodes including transcript chunks.

    Returns a dict mapping entity/session/chunk ID to its embedding vector.
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

    # Presentation nodes — embed summary + title
    if presentations_data:
        for pres in presentations_data:
            texts_by_id[pres["id"]] = f"{pres['title']}. {pres.get('summary', '')[:500]}".strip()

    # Transcript chunk nodes — embed chunk content with presentation context
    if transcript_chunks:
        for chunk in transcript_chunks:
            texts_by_id[chunk.id] = chunk.content[:2000]

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
            continue

    logger.info("Generated %d embeddings (dimension=%d)", len(embeddings), 3072)
    return embeddings


def run_embed(
    entities: list[Entity],
    sessions_data: list[dict],
    api_key: str,
    presentations_data: list[dict] | None = None,
    transcript_chunks: list[TranscriptChunk] | None = None,
) -> dict[str, list[float]]:
    """Synchronous convenience wrapper for embed_all_nodes."""
    from pipeline.llm_utils import get_base_url

    client = AsyncOpenAI(
        base_url=get_base_url(),
        api_key=api_key,
    )
    return asyncio.run(
        embed_all_nodes(
            entities,
            sessions_data,
            client,
            presentations_data=presentations_data,
            transcript_chunks=transcript_chunks,
        )
    )


def embeddings_to_serializable(embeddings: dict[str, list[float]]) -> dict[str, Any]:
    """Convert embeddings dict to JSON-serializable format."""
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

    from pipeline.llm_utils import get_api_key

    embeddings = run_embed(
        extraction.entities,
        sessions_data,
        get_api_key(),
    )
    print(f"Generated {len(embeddings)} embeddings")

    out = cache_dir / "embed_output.json"
    out.write_text(json.dumps(embeddings, indent=None, ensure_ascii=False))
    print(f"Wrote {out}")
