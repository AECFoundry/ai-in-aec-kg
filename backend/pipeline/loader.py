"""Load extracted graph data into Neo4j."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import neo4j

from pipeline.embedder import TranscriptChunk
from pipeline.extractor import Entity, ExtractionResult, Relationship
from pipeline.presentation_extractor import Presentation
from pipeline.schema import create_schema

logger = logging.getLogger(__name__)

# Valid Neo4j labels (must start with letter, contain only alphanum/underscore)
VALID_LABELS = {"Session", "Speaker", "Organization", "Topic", "Technology", "Concept", "Project", "Presentation", "TranscriptChunk"}


def _sanitize_label(label: str) -> str:
    """Ensure a label is a valid Neo4j label name."""
    label = label.strip().title()
    if label in VALID_LABELS:
        return label
    # Fallback for unknown types
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", label)
    return cleaned if cleaned else "Entity"


def _sanitize_rel_type(rel_type: str) -> str:
    """Ensure a relationship type is valid for Neo4j."""
    cleaned = re.sub(r"[^A-Z0-9_]", "_", rel_type.upper())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned if cleaned else "RELATES_TO"


async def _load_nodes(
    session: neo4j.AsyncSession,
    entities: list[Entity],
    embeddings: dict[str, list[float]],
) -> None:
    """Load entity nodes into Neo4j."""
    for entity in entities:
        label = _sanitize_label(entity.type)
        props: dict[str, Any] = {
            "name": entity.name,
            "description": entity.description,
            "source_sessions": entity.source_sessions,
        }

        # Add embedding if available
        embedding = embeddings.get(entity.id)
        if embedding:
            props["embedding"] = embedding

        query = f"MERGE (n:{label} {{id: $id}}) SET n += $props"
        try:
            await session.run(query, id=entity.id, props=props)
        except Exception as exc:
            logger.error("Failed to load node %s (%s): %s", entity.id, label, exc)


async def _load_session_nodes(
    session: neo4j.AsyncSession,
    sessions_data: list[dict],
    embeddings: dict[str, list[float]],
) -> None:
    """Load session nodes with full text data."""
    for s in sessions_data:
        sid = f"session_{s['session_number']}"
        props: dict[str, Any] = {
            "name": s["title"],
            "session_number": s["session_number"],
            "title": s["title"],
            "summary_text": s.get("summary_text", ""),
            "description": (s.get("summary_text", "") or s["title"])[:500],
        }
        embedding = embeddings.get(sid)
        if embedding:
            props["embedding"] = embedding

        query = "MERGE (n:Session {id: $id}) SET n += $props"
        try:
            await session.run(query, id=sid, props=props)
        except Exception as exc:
            logger.error("Failed to load session node %s: %s", sid, exc)


async def _load_relationships(
    session: neo4j.AsyncSession,
    relationships: list[Relationship],
) -> None:
    """Load relationships into Neo4j."""
    for rel in relationships:
        rel_type = _sanitize_rel_type(rel.type)
        props: dict[str, Any] = {}
        if rel.description:
            props["description"] = rel.description
        if rel.properties:
            # Only include serializable properties
            for k, v in rel.properties.items():
                if isinstance(v, (str, int, float, bool)):
                    props[k] = v

        query = (
            f"MATCH (a {{id: $source_id}}), (b {{id: $target_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            f"SET r += $props"
        )
        try:
            await session.run(
                query,
                source_id=rel.source_id,
                target_id=rel.target_id,
                props=props,
            )
        except Exception as exc:
            logger.warning(
                "Failed to load relationship %s -[%s]-> %s: %s",
                rel.source_id,
                rel_type,
                rel.target_id,
                exc,
            )


async def _load_presentations(
    session: neo4j.AsyncSession,
    presentations: list[Presentation],
    embeddings: dict[str, list[float]],
) -> None:
    """Load presentation nodes and their relationships into Neo4j."""
    # Remove stale Presentation nodes not in the current batch to avoid
    # duplicates when the LLM produces slightly different titles across runs.
    current_ids = [p.id for p in presentations]
    try:
        result = await session.run(
            "MATCH (p:Presentation) WHERE NOT p.id IN $ids "
            "DETACH DELETE p RETURN count(p) AS deleted",
            ids=current_ids,
        )
        record = await result.single()
        deleted = record["deleted"] if record else 0
        if deleted:
            logger.info("Removed %d stale Presentation nodes from previous runs", deleted)
    except Exception as exc:
        logger.warning("Failed to clean stale presentations: %s", exc)

    for pres in presentations:
        props: dict[str, Any] = {
            "name": pres.title,
            "title": pres.title,
            "summary": pres.summary,
            "description": pres.summary[:500],
            "order": pres.order,
            "session_id": pres.session_id,
        }
        if pres.transcript:
            props["transcript"] = pres.transcript
        embedding = embeddings.get(pres.id)
        if embedding:
            props["embedding"] = embedding

        # Create Presentation node
        try:
            await session.run(
                "MERGE (n:Presentation {id: $id}) SET n += $props",
                id=pres.id,
                props=props,
            )
        except Exception as exc:
            logger.error("Failed to load presentation %s: %s", pres.id, exc)
            continue

        # PART_OF -> Session
        try:
            await session.run(
                "MATCH (p:Presentation {id: $pres_id}), (s:Session {id: $sess_id}) "
                "MERGE (p)-[r:PART_OF]->(s) SET r.order = $order",
                pres_id=pres.id,
                sess_id=pres.session_id,
                order=pres.order,
            )
        except Exception as exc:
            logger.warning("Failed to link presentation %s -> %s: %s", pres.id, pres.session_id, exc)

        # PRESENTED_BY -> Speaker (fuzzy match by name)
        for speaker_name in pres.speakers:
            # Find speaker node by case-insensitive name match
            try:
                result = await session.run(
                    "MATCH (sp:Speaker) WHERE toLower(sp.name) = toLower($name) RETURN sp.id AS id LIMIT 1",
                    name=speaker_name,
                )
                record = await result.single()
                if record:
                    await session.run(
                        "MATCH (p:Presentation {id: $pres_id}), (sp:Speaker {id: $speaker_id}) "
                        "MERGE (p)-[:PRESENTED_BY]->(sp)",
                        pres_id=pres.id,
                        speaker_id=record["id"],
                    )
            except Exception as exc:
                logger.warning("Failed to link presentation to speaker %s: %s", speaker_name, exc)


async def _load_transcript_chunks(
    session: neo4j.AsyncSession,
    chunks: list[TranscriptChunk],
    embeddings: dict[str, list[float]],
) -> None:
    """Load transcript chunk nodes and CHUNK_OF relationships."""
    for chunk in chunks:
        props: dict[str, Any] = {
            "name": f"Chunk {chunk.chunk_index + 1}/{chunk.total_chunks}",
            "content": chunk.content,
            "chunk_index": chunk.chunk_index,
            "total_chunks": chunk.total_chunks,
            "presentation_id": chunk.presentation_id,
            "session_id": chunk.session_id,
        }
        embedding = embeddings.get(chunk.id)
        if embedding:
            props["embedding"] = embedding

        try:
            await session.run(
                "MERGE (n:TranscriptChunk {id: $id}) SET n += $props",
                id=chunk.id,
                props=props,
            )
        except Exception as exc:
            logger.error("Failed to load chunk %s: %s", chunk.id, exc)
            continue

        # CHUNK_OF -> Presentation
        try:
            await session.run(
                "MATCH (c:TranscriptChunk {id: $chunk_id}), (p:Presentation {id: $pres_id}) "
                "MERGE (c)-[r:CHUNK_OF]->(p) SET r.chunk_index = $idx",
                chunk_id=chunk.id,
                pres_id=chunk.presentation_id,
                idx=chunk.chunk_index,
            )
        except Exception as exc:
            logger.warning("Failed to link chunk %s -> %s: %s", chunk.id, chunk.presentation_id, exc)


async def _link_orphans_to_sessions(session: neo4j.AsyncSession) -> None:
    """Ensure every entity with source_sessions has at least one link to a Session.

    Entities may be extracted or enriched from sessions/presentations but end up
    with no relationship path back to any Session node.  This creates MENTIONS
    links so the graph has no disconnected subgraphs.
    """
    result = await session.run(
        """
        MATCH (n)
        WHERE n.source_sessions IS NOT NULL
          AND size(n.source_sessions) > 0
          AND NOT n:Session
          AND NOT n:Presentation
        WITH n
        WHERE NOT exists { MATCH (n)-[]-(:Session) }
        UNWIND n.source_sessions AS snum
        WITH n, "session_" + toString(snum) AS sid
        MATCH (s:Session {id: sid})
        MERGE (s)-[r:MENTIONS]->(n)
        RETURN count(r) AS created
        """
    )
    record = await result.single()
    count = record["created"] if record else 0
    if count:
        logger.info("Created %d MENTIONS links for orphaned entities", count)


async def load_graph(
    driver: neo4j.AsyncDriver,
    sessions_data: list[dict],
    entities: list[Entity],
    relationships: list[Relationship],
    embeddings: dict[str, list[float]],
    presentations: list[Presentation] | None = None,
    transcript_chunks: list[TranscriptChunk] | None = None,
) -> None:
    """Load the full graph into Neo4j.

    Uses MERGE everywhere for idempotency.
    """
    async with driver.session() as session:
        # 1. Create schema (constraints + vector indexes)
        logger.info("Creating schema...")
        await create_schema(session)

        # 2. Load session nodes first (with full text)
        logger.info("Loading %d session nodes...", len(sessions_data))
        await _load_session_nodes(session, sessions_data, embeddings)

        # 3. Load entity nodes (excluding sessions, which are already loaded)
        non_session_entities = [e for e in entities if e.type != "Session"]
        logger.info("Loading %d entity nodes...", len(non_session_entities))
        await _load_nodes(session, non_session_entities, embeddings)

        # 4. Load presentations (before relationships so enrichment links resolve)
        if presentations:
            logger.info("Loading %d presentations...", len(presentations))
            await _load_presentations(session, presentations, embeddings)

        # 5. Load transcript chunks
        if transcript_chunks:
            logger.info("Loading %d transcript chunks...", len(transcript_chunks))
            await _load_transcript_chunks(session, transcript_chunks, embeddings)

        # 6. Load relationships
        logger.info("Loading %d relationships...", len(relationships))
        await _load_relationships(session, relationships)

        # 7. Ensure every entity is linked to its source session(s)
        logger.info("Linking orphaned entities to source sessions...")
        await _link_orphans_to_sessions(session)

        # 8. Remove fully disconnected nodes (e.g. topics orphaned by stale presentation cleanup)
        result = await session.run(
            "MATCH (n) WHERE NOT exists { MATCH (n)-[]-() } "
            "DELETE n RETURN count(n) AS deleted"
        )
        record = await result.single()
        orphan_count = record["deleted"] if record else 0
        if orphan_count:
            logger.info("Removed %d fully disconnected nodes", orphan_count)

    logger.info("Graph loading complete")


def run_load(
    sessions_data: list[dict],
    entities: list[Entity],
    relationships: list[Relationship],
    embeddings: dict[str, list[float]],
    presentations: list[Presentation] | None = None,
    transcript_chunks: list[TranscriptChunk] | None = None,
    *,
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "",
) -> None:
    """Synchronous convenience wrapper for load_graph."""

    async def _run():
        driver = neo4j.AsyncGraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password),
        )
        try:
            await load_graph(driver, sessions_data, entities, relationships, embeddings, presentations, transcript_chunks)
        finally:
            await driver.close()

    asyncio.run(_run())


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
    embed_path = cache_dir / "embed_output.json"

    for path, name in [
        (enrich_path, "enrich"),
        (parse_path, "parse"),
        (embed_path, "embed"),
    ]:
        if not path.exists():
            print(f"No {name} output at {path}. Run {name} stage first.")
            raise SystemExit(1)

    enrich_data = json.loads(enrich_path.read_text(encoding="utf-8"))
    sessions_data = json.loads(parse_path.read_text(encoding="utf-8"))
    embeddings = json.loads(embed_path.read_text(encoding="utf-8"))

    extraction = ExtractionResult.from_dict(enrich_data)

    run_load(
        sessions_data=sessions_data,
        entities=extraction.entities,
        relationships=extraction.relationships,
        embeddings=embeddings,
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", ""),
    )
    print("Loading complete")
