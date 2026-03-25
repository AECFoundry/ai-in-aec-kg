"""NLP-based enrichment using spaCy NER and KeyBERT keyword extraction."""

from __future__ import annotations

import logging
import re

from pipeline.extractor import Entity, ExtractionResult, Relationship

logger = logging.getLogger(__name__)

# Map spaCy NER labels to our entity types
SPACY_LABEL_MAP = {
    "ORG": "Organization",
    "PRODUCT": "Technology",
    "PERSON": "Speaker",
    "GPE": "Organization",  # Geo-political entities often map to orgs in this context
}


def _slugify(text: str) -> str:
    """Convert a string to a slug suitable for use as an ID."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    text = re.sub(r"-+", "_", text)
    return text.strip("_")


def _make_entity_id(entity_type: str, name: str) -> str:
    prefix = _slugify(entity_type)
    slug = _slugify(name)
    return f"{prefix}_{slug}"


def _normalize_for_match(name: str) -> str:
    return name.lower().strip().rstrip(".,;:!?")


def _entity_exists(name: str, entity_index: dict[str, Entity]) -> bool:
    """Check if an entity with a similar name already exists."""
    normalized = _normalize_for_match(name)
    if len(normalized) < 3:
        return True  # Skip very short names
    for entity in entity_index.values():
        if _normalize_for_match(entity.name) == normalized:
            return True
    return False


def enrich_graph(
    sessions_data: list[dict],
    entities: list[Entity],
    relationships: list[Relationship],
) -> tuple[list[Entity], list[Relationship]]:
    """Enrich the graph with spaCy NER and KeyBERT keywords.

    Args:
        sessions_data: List of session dicts (from parser, with live_text and summary_text).
        entities: Current entity list.
        relationships: Current relationship list.

    Returns:
        Enriched entities and relationships.
    """
    import spacy

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.warning(
            "spaCy model 'en_core_web_sm' not found. "
            "Install with: python -m spacy download en_core_web_sm"
        )
        return entities, relationships

    entity_index: dict[str, Entity] = {e.id: e for e in entities}
    new_entities: list[Entity] = []
    new_relationships: list[Relationship] = []

    # --- spaCy NER enrichment ---
    for session_dict in sessions_data:
        session_number = session_dict["session_number"]
        live_text = session_dict.get("live_text", "")
        # Process live_text through spaCy (limit length for performance)
        text = live_text[:10000] if live_text else ""
        if not text:
            continue

        doc = nlp(text)
        session_id = f"session_{session_number}"

        for ent in doc.ents:
            if ent.label_ not in SPACY_LABEL_MAP:
                continue
            name = ent.text.strip()
            if len(name) < 3 or len(name) > 80:
                continue
            entity_type = SPACY_LABEL_MAP[ent.label_]

            if _entity_exists(name, entity_index):
                continue

            eid = _make_entity_id(entity_type, name)
            if eid in entity_index:
                # Update source sessions
                existing = entity_index[eid]
                if session_number not in existing.source_sessions:
                    existing.source_sessions.append(session_number)
                continue

            new_entity = Entity(
                id=eid,
                name=name,
                type=entity_type,
                description=(
                    f"{name} ({entity_type}, discovered"
                    f" via NER from session {session_number})"
                ),
                source_sessions=[session_number],
            )
            entity_index[eid] = new_entity
            new_entities.append(new_entity)

            # Relate to session
            new_relationships.append(Relationship(
                source_id=session_id,
                target_id=eid,
                type="MENTIONS",
                description=f"Session {session_number} mentions {name}",
                properties={"source": "spacy_ner"},
            ))

    logger.info("spaCy NER found %d new entities", len(new_entities))

    # --- KeyBERT keyword extraction ---
    try:
        from keybert import KeyBERT

        kw_model = KeyBERT()

        for session_dict in sessions_data:
            session_number = session_dict["session_number"]
            summary_text = session_dict.get("summary_text", "")
            if not summary_text or len(summary_text) < 50:
                continue

            try:
                keywords = kw_model.extract_keywords(
                    summary_text,
                    keyphrase_ngram_range=(1, 3),
                    stop_words="english",
                    top_n=5,
                    use_maxsum=True,
                    nr_candidates=20,
                )
            except Exception as exc:
                logger.warning(
                    "KeyBERT extraction failed for session %d: %s",
                    session_number,
                    exc,
                )
                continue

            session_id = f"session_{session_number}"

            for keyword, score in keywords:
                keyword = keyword.strip()
                if len(keyword) < 3:
                    continue
                tid = _make_entity_id("topic", keyword)
                if tid not in entity_index:
                    topic_entity = Entity(
                        id=tid,
                        name=keyword.title(),
                        type="Topic",
                        description=f"Keyword topic extracted from session {session_number}",
                        source_sessions=[session_number],
                    )
                    entity_index[tid] = topic_entity
                    new_entities.append(topic_entity)
                else:
                    existing = entity_index[tid]
                    if session_number not in existing.source_sessions:
                        existing.source_sessions.append(session_number)

                new_relationships.append(Relationship(
                    source_id=session_id,
                    target_id=tid,
                    type="COVERS_TOPIC",
                    description=f"Keyword '{keyword}' (score={score:.2f})",
                    properties={"source": "keybert", "score": round(score, 3)},
                ))

        logger.info("KeyBERT added topics, total new entities: %d", len(new_entities))

    except ImportError:
        logger.warning("KeyBERT not available, skipping keyword extraction")

    enriched_entities = entities + new_entities
    enriched_relationships = relationships + new_relationships
    return enriched_entities, enriched_relationships


def enrich(
    sessions_data: list[dict],
    extraction_result: ExtractionResult,
) -> ExtractionResult:
    """Convenience wrapper that takes and returns an ExtractionResult."""
    entities, relationships = enrich_graph(
        sessions_data, extraction_result.entities, extraction_result.relationships
    )
    return ExtractionResult(entities=entities, relationships=relationships)


if __name__ == "__main__":
    import json
    from pathlib import Path

    logging.basicConfig(level=logging.INFO)

    cache_dir = Path(__file__).resolve().parents[1] / "data" / "pipeline_cache"
    resolve_path = cache_dir / "resolve_output.json"
    parse_path = cache_dir / "parse_output.json"

    if not resolve_path.exists():
        print(f"No resolve output at {resolve_path}. Run resolve stage first.")
        raise SystemExit(1)
    if not parse_path.exists():
        print(f"No parse output at {parse_path}. Run parse stage first.")
        raise SystemExit(1)

    resolve_data = json.loads(resolve_path.read_text(encoding="utf-8"))
    sessions_data = json.loads(parse_path.read_text(encoding="utf-8"))
    extraction = ExtractionResult.from_dict(resolve_data)

    result = enrich(sessions_data, extraction)
    print(
        f"Enriched: {len(result.entities)} entities, "
        f"{len(result.relationships)} relationships"
    )

    out = cache_dir / "enrich_output.json"
    out.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    print(f"Wrote {out}")
