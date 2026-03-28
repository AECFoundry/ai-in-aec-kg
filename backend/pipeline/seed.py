"""Load pre-built seed data into Neo4j — no pipeline or API keys required.

Usage:
    cd backend && uv run python -m pipeline.seed
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed")

SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed"


def _load_json(filename: str) -> dict | list:
    path = SEED_DIR / filename
    if not path.exists():
        logger.error("Missing seed file: %s", path)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def _load_gzipped_json(filename: str) -> dict:
    path = SEED_DIR / filename
    if not path.exists():
        logger.error("Missing seed file: %s", path)
        sys.exit(1)
    with gzip.open(path, "rb") as f:
        return json.loads(f.read())


def main() -> None:
    import asyncio

    import neo4j

    from pipeline.embedder import TranscriptChunk
    from pipeline.extractor import ExtractionResult
    from pipeline.loader import load_graph
    from pipeline.presentation_extractor import Presentation

    logger.info("Loading seed data from %s", SEED_DIR)

    # Load all seed files
    sessions_data = _load_json("parse_output.json")
    enrich_data = _load_json("enrich_output.json")
    presentations_data = _load_json("presentations_output.json")
    chunks_data = _load_json("chunks_output.json")

    logger.info("Decompressing embeddings (this may take a moment)...")
    embeddings = _load_gzipped_json("embed_output.json.gz")

    # Deserialize
    extraction = ExtractionResult.from_dict(enrich_data)
    presentations = [Presentation.from_dict(p) for p in presentations_data]
    chunks = [TranscriptChunk.from_dict(c) for c in chunks_data]

    logger.info(
        "Seed data: %d sessions, %d entities, %d relationships, %d presentations, %d chunks, %d embeddings",
        len(sessions_data),
        len(extraction.entities),
        len(extraction.relationships),
        len(presentations),
        len(chunks),
        len(embeddings),
    )

    # Load into Neo4j
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "")

    # Extract detailed summaries to apply after loading
    detailed_summaries = {
        p["id"]: p["detailed_summary"]
        for p in presentations_data
        if p.get("detailed_summary")
    }

    async def _run() -> None:
        driver = neo4j.AsyncGraphDatabase.driver(
            neo4j_uri, auth=(neo4j_user, neo4j_password)
        )
        try:
            await load_graph(
                driver,
                sessions_data=sessions_data,
                entities=extraction.entities,
                relationships=extraction.relationships,
                embeddings=embeddings,
                presentations=presentations,
                transcript_chunks=chunks,
            )

            # Apply detailed summaries (not part of Presentation dataclass)
            if detailed_summaries:
                logger.info("Writing %d detailed summaries...", len(detailed_summaries))
                async with driver.session() as session:
                    for pres_id, summary in detailed_summaries.items():
                        await session.run(
                            "MATCH (p:Presentation {id: $id}) SET p.detailed_summary = $summary",
                            id=pres_id,
                            summary=summary,
                        )
                logger.info("Detailed summaries applied")
        finally:
            await driver.close()

    asyncio.run(_run())
    logger.info("Seed complete — graph is ready!")


if __name__ == "__main__":
    main()
