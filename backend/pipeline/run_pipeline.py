"""CLI entry point for the graph extraction pipeline.

Usage:
    python -m pipeline.run_pipeline [--stage STAGE] [--source PATH]

Stages in order: parse, extract, resolve, enrich, embed, load
- Default: run all stages
- --stage: run only that stage (loads intermediate results from JSON cache)
- --source: path to source file
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")

logger = logging.getLogger("pipeline")

STAGES = ["parse", "extract", "resolve", "presentations", "enrich", "embed", "load"]
CACHE_DIR = _BACKEND_DIR / "data" / "pipeline_cache"

DEFAULT_SOURCE = _REPO_ROOT / "AI_in_AEC_2026_Snapsight_Summaries.txt"


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(stage: str) -> Path:
    return CACHE_DIR / f"{stage}_output.json"


def _save_cache(stage: str, data) -> None:
    _ensure_cache_dir()
    path = _cache_path(stage)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    logger.info("Saved %s output to %s", stage, path)


def _load_cache(stage: str):
    path = _cache_path(stage)
    if not path.exists():
        logger.error("Cache file not found: %s. Run the '%s' stage first.", path, stage)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------


def run_parse(source: Path) -> list[dict]:
    """Parse the source file into session objects."""
    from pipeline.parser import parse_transcripts

    logger.info("Parsing %s", source)
    sessions = parse_transcripts(source)
    logger.info("Parsed %d sessions", len(sessions))

    data = [s.to_dict() for s in sessions]
    _save_cache("parse", data)
    return data


def run_extract(sessions_data: list[dict] | None = None) -> dict:
    """Extract entities and relationships from session summaries via LLM."""
    from openai import OpenAI

    from pipeline.extractor import extract_all
    from pipeline.llm_utils import get_api_key, get_base_url
    from pipeline.parser import SessionChunk

    if sessions_data is None:
        sessions_data = _load_cache("parse")

    sessions = [SessionChunk.from_dict(d) for d in sessions_data]

    client = OpenAI(
        base_url=get_base_url(),
        api_key=get_api_key(),
    )

    result = extract_all(sessions, client)
    logger.info(
        "Extracted %d entities, %d relationships",
        len(result.entities),
        len(result.relationships),
    )

    data = result.to_dict()
    _save_cache("extract", data)
    return data


def run_resolve(extract_data: dict | None = None) -> dict:
    """Resolve/deduplicate entities."""
    from pipeline.entity_resolution import resolve
    from pipeline.extractor import ExtractionResult

    if extract_data is None:
        extract_data = _load_cache("extract")

    extraction = ExtractionResult.from_dict(extract_data)
    result = resolve(extraction)
    logger.info(
        "Resolved to %d entities, %d relationships",
        len(result.entities),
        len(result.relationships),
    )

    data = result.to_dict()
    _save_cache("resolve", data)
    return data


def run_enrich(
    resolve_data: dict | None = None,
    sessions_data: list[dict] | None = None,
    presentations_data: list[dict] | None = None,
) -> dict:
    """Enrich graph with spaCy NER and KeyBERT keywords."""
    from pipeline.enrichment import enrich
    from pipeline.extractor import ExtractionResult

    if resolve_data is None:
        resolve_data = _load_cache("resolve")
    if sessions_data is None:
        sessions_data = _load_cache("parse")
    if presentations_data is None:
        try:
            presentations_data = _load_cache("presentations")
        except SystemExit:
            presentations_data = None

    extraction = ExtractionResult.from_dict(resolve_data)
    result = enrich(sessions_data, extraction, presentations_data=presentations_data)
    logger.info(
        "Enriched to %d entities, %d relationships",
        len(result.entities),
        len(result.relationships),
    )

    data = result.to_dict()
    _save_cache("enrich", data)
    return data


def run_presentations(sessions_data: list[dict] | None = None) -> list[dict]:
    """Extract individual presentations from session summaries via LLM."""
    from openai import OpenAI

    from pipeline.llm_utils import get_api_key, get_base_url
    from pipeline.presentation_extractor import extract_presentations

    if sessions_data is None:
        sessions_data = _load_cache("parse")

    client = OpenAI(
        base_url=get_base_url(),
        api_key=get_api_key(),
    )

    presentations = extract_presentations(sessions_data, client)
    logger.info("Extracted %d presentations", len(presentations))

    data = [p.to_dict() for p in presentations]
    _save_cache("presentations", data)
    return data


def run_embed(
    enrich_data: dict | None = None,
    sessions_data: list[dict] | None = None,
    presentations_data: list[dict] | None = None,
) -> tuple[dict, list[dict]]:
    """Generate embeddings for all nodes, including transcript chunks.

    Returns (embeddings_dict, chunks_data_list).
    """
    from pipeline.embedder import TranscriptChunk, build_transcript_chunks
    from pipeline.embedder import run_embed as _run_embed
    from pipeline.extractor import ExtractionResult

    if enrich_data is None:
        enrich_data = _load_cache("enrich")
    if sessions_data is None:
        sessions_data = _load_cache("parse")
    if presentations_data is None:
        try:
            presentations_data = _load_cache("presentations")
        except SystemExit:
            presentations_data = None

    from pipeline.llm_utils import get_api_key

    # Build transcript chunks from presentations
    chunks: list[TranscriptChunk] = []
    if presentations_data:
        chunks = build_transcript_chunks(presentations_data)
        logger.info("Built %d transcript chunks", len(chunks))

    extraction = ExtractionResult.from_dict(enrich_data)
    embeddings = _run_embed(
        extraction.entities, sessions_data, get_api_key(),
        presentations_data, chunks or None,
    )
    logger.info("Generated %d embeddings", len(embeddings))

    _save_cache("embed", embeddings)
    chunks_data = [c.to_dict() for c in chunks]
    _save_cache("chunks", chunks_data)
    return embeddings, chunks_data


def run_load(
    enrich_data: dict | None = None,
    sessions_data: list[dict] | None = None,
    embeddings: dict | None = None,
    presentations_data: list[dict] | None = None,
    chunks_data: list[dict] | None = None,
) -> None:
    """Load everything into Neo4j."""
    from pipeline.embedder import TranscriptChunk
    from pipeline.extractor import ExtractionResult
    from pipeline.loader import run_load as _run_load
    from pipeline.presentation_extractor import Presentation

    if enrich_data is None:
        enrich_data = _load_cache("enrich")
    if sessions_data is None:
        sessions_data = _load_cache("parse")
    if embeddings is None:
        embeddings = _load_cache("embed")
    if presentations_data is None:
        try:
            presentations_data = _load_cache("presentations")
        except SystemExit:
            presentations_data = None
    if chunks_data is None:
        try:
            chunks_data = _load_cache("chunks")
        except SystemExit:
            chunks_data = None

    extraction = ExtractionResult.from_dict(enrich_data)
    presentations = (
        [Presentation.from_dict(p) for p in presentations_data]
        if presentations_data
        else None
    )
    chunks = (
        [TranscriptChunk.from_dict(c) for c in chunks_data]
        if chunks_data
        else None
    )

    _run_load(
        sessions_data=sessions_data,
        entities=extraction.entities,
        relationships=extraction.relationships,
        embeddings=embeddings,
        presentations=presentations,
        transcript_chunks=chunks,
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", ""),
    )
    logger.info("Graph loaded into Neo4j")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="AI in AEC Knowledge Graph extraction pipeline"
    )
    parser.add_argument(
        "--stage",
        choices=STAGES,
        default=None,
        help="Run only this stage (default: run all stages in order)",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Path to source transcript file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    _ensure_cache_dir()

    if args.stage:
        stages_to_run = [args.stage]
    else:
        stages_to_run = STAGES

    # Track data flowing between stages
    sessions_data = None
    extract_data = None
    resolve_data = None
    enrich_data = None
    presentations_data = None
    embeddings = None
    chunks_data = None

    for stage in stages_to_run:
        logger.info("=" * 60)
        logger.info("STAGE: %s", stage.upper())
        logger.info("=" * 60)

        if stage == "parse":
            sessions_data = run_parse(args.source)

        elif stage == "extract":
            extract_data = run_extract(sessions_data)

        elif stage == "resolve":
            resolve_data = run_resolve(extract_data)

        elif stage == "enrich":
            enrich_data = run_enrich(resolve_data, sessions_data, presentations_data)

        elif stage == "presentations":
            presentations_data = run_presentations(sessions_data)

        elif stage == "embed":
            embeddings, chunks_data = run_embed(enrich_data, sessions_data, presentations_data)

        elif stage == "load":
            run_load(enrich_data, sessions_data, embeddings, presentations_data, chunks_data)

    logger.info("=" * 60)
    logger.info("Pipeline complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
