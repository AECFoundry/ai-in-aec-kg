"""One-time script to generate seed data from pipeline cache + Neo4j.

Produces the files in backend/data/seed/ that ship with the repo so new users
can load the graph without running the extraction pipeline.

Usage:
    cd backend && uv run python data/seed/prepare_seed.py

Prerequisites:
    - Pipeline cache populated (all stages run)
    - Neo4j running with detailed_summary values on Presentation nodes
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = Path(__file__).resolve().parents[1] / "pipeline_cache"
SEED_DIR = Path(__file__).resolve().parent

load_dotenv(REPO_ROOT / ".env")

# Files to copy as-is from pipeline cache
COPY_FILES = [
    "parse_output.json",
    "extract_output.json",
    "resolve_output.json",
    "enrich_output.json",
    "chunks_output.json",
]


async def export_detailed_summaries() -> dict[str, str]:
    """Fetch detailed_summary from Neo4j Presentation nodes."""
    driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
    )
    async with driver.session() as session:
        result = await session.run(
            "MATCH (p:Presentation) WHERE p.detailed_summary IS NOT NULL "
            "RETURN p.id AS id, p.detailed_summary AS detailed_summary"
        )
        records = await result.data()
    await driver.close()
    return {r["id"]: r["detailed_summary"] for r in records}


def merge_presentations_with_summaries(summaries: dict[str, str]) -> None:
    """Merge detailed_summary into presentations_output.json and write to seed."""
    src = CACHE_DIR / "presentations_output.json"
    presentations = json.loads(src.read_text(encoding="utf-8"))

    merged = 0
    for pres in presentations:
        summary = summaries.get(pres["id"])
        if summary:
            pres["detailed_summary"] = summary
            merged += 1

    dest = SEED_DIR / "presentations_output.json"
    dest.write_text(json.dumps(presentations, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %s (%d presentations, %d with detailed_summary)", dest.name, len(presentations), merged)


def compress_embeddings() -> None:
    """Round embedding floats to 6 decimal places and gzip."""
    src = CACHE_DIR / "embed_output.json"
    embeddings = json.loads(src.read_text(encoding="utf-8"))

    # Round floats to 6 decimal places
    rounded = {}
    for key, vec in embeddings.items():
        rounded[key] = [round(v, 6) for v in vec]

    json_bytes = json.dumps(rounded, ensure_ascii=False).encode("utf-8")
    dest = SEED_DIR / "embed_output.json.gz"
    with gzip.open(dest, "wb", compresslevel=9) as f:
        f.write(json_bytes)

    src_mb = src.stat().st_size / (1024 * 1024)
    dest_mb = dest.stat().st_size / (1024 * 1024)
    logger.info(
        "Compressed embeddings: %.1fMB -> %.1fMB (%.0f%% reduction)",
        src_mb, dest_mb, (1 - dest_mb / src_mb) * 100,
    )


async def main() -> None:
    # 1. Copy plain JSON files
    for filename in COPY_FILES:
        src = CACHE_DIR / filename
        if not src.exists():
            logger.error("Missing cache file: %s", src)
            continue
        dest = SEED_DIR / filename
        shutil.copy2(src, dest)
        size_kb = dest.stat().st_size / 1024
        logger.info("Copied %s (%.0fKB)", filename, size_kb)

    # 2. Export detailed summaries and merge into presentations
    logger.info("Exporting detailed summaries from Neo4j...")
    summaries = await export_detailed_summaries()
    logger.info("Found %d detailed summaries", len(summaries))
    merge_presentations_with_summaries(summaries)

    # 3. Compress embeddings
    logger.info("Compressing embeddings...")
    compress_embeddings()

    # Summary
    logger.info("Seed data ready in %s", SEED_DIR)


if __name__ == "__main__":
    asyncio.run(main())
