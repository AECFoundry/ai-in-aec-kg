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
    presentations_data: list[dict] | None = None,
) -> tuple[list[Entity], list[Relationship]]:
    """Enrich the graph with spaCy NER and KeyBERT keywords.

    Processes:
    - Session live_text for NER
    - Presentation formatted transcripts for NER
    - Session summaries for KeyBERT
    - Presentation transcripts for KeyBERT (richer than summaries alone)

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

    def _add_ner_entity(name: str, entity_type: str, source_id: str, session_number: int | None):
        """Add NER-discovered entity and MENTIONS relationship."""
        name = name.strip()
        if len(name) < 3 or len(name) > 80:
            return
        if _entity_exists(name, entity_index):
            return

        eid = _make_entity_id(entity_type, name)
        if eid in entity_index:
            existing = entity_index[eid]
            if session_number and session_number not in existing.source_sessions:
                existing.source_sessions.append(session_number)
            return

        source_sessions = [session_number] if session_number else []
        new_entity = Entity(
            id=eid,
            name=name,
            type=entity_type,
            description=f"{name} ({entity_type}, discovered via NER)",
            source_sessions=source_sessions,
        )
        entity_index[eid] = new_entity
        new_entities.append(new_entity)

        new_relationships.append(Relationship(
            source_id=source_id,
            target_id=eid,
            type="MENTIONS",
            description=f"{source_id} mentions {name}",
            properties={"source": "spacy_ner"},
        ))

    # --- spaCy NER on session live_text ---
    for session_dict in sessions_data:
        session_number = session_dict["session_number"]
        live_text = session_dict.get("live_text", "")
        text = live_text[:10000] if live_text else ""
        if not text:
            continue

        doc = nlp(text)
        session_id = f"session_{session_number}"

        for ent in doc.ents:
            if ent.label_ not in SPACY_LABEL_MAP:
                continue
            _add_ner_entity(ent.text, SPACY_LABEL_MAP[ent.label_], session_id, session_number)

    # --- spaCy NER on presentation transcripts ---
    pres_ner_count = 0
    if presentations_data:
        for pres in presentations_data:
            pres_id = pres.get("id", "")
            transcript = pres.get("transcript", "")
            if not transcript or len(transcript) < 50:
                continue

            # Process full transcript (formatted, so cleaner than raw live_text)
            doc = nlp(transcript[:15000])
            session_id = pres.get("session_id", "")
            # Extract session number from session_id
            session_number = None
            if session_id.startswith("session_"):
                try:
                    session_number = int(session_id.split("_")[1])
                except (IndexError, ValueError):
                    pass

            before = len(new_entities)
            for ent in doc.ents:
                if ent.label_ not in SPACY_LABEL_MAP:
                    continue
                _add_ner_entity(ent.text, SPACY_LABEL_MAP[ent.label_], pres_id, session_number)
            pres_ner_count += len(new_entities) - before

    logger.info(
        "spaCy NER found %d new entities (%d from presentation transcripts)",
        len(new_entities),
        pres_ner_count,
    )

    # --- KeyBERT keyword extraction ---
    try:
        from keybert import KeyBERT

        kw_model = KeyBERT()

        def _extract_topics(text: str, source_id: str, session_number: int | None, top_n: int = 5):
            """Extract keywords from text and create Topic entities + relationships."""
            if not text or len(text) < 50:
                return
            try:
                keywords = kw_model.extract_keywords(
                    text,
                    keyphrase_ngram_range=(1, 3),
                    stop_words="english",
                    top_n=top_n,
                    use_maxsum=True,
                    nr_candidates=20,
                )
            except Exception as exc:
                logger.warning("KeyBERT extraction failed for %s: %s", source_id, exc)
                return

            for keyword, score in keywords:
                keyword = keyword.strip()
                if len(keyword) < 3:
                    continue
                tid = _make_entity_id("topic", keyword)
                if tid not in entity_index:
                    source_sessions = [session_number] if session_number else []
                    topic_entity = Entity(
                        id=tid,
                        name=keyword.title(),
                        type="Topic",
                        description=f"Keyword topic extracted from {source_id}",
                        source_sessions=source_sessions,
                    )
                    entity_index[tid] = topic_entity
                    new_entities.append(topic_entity)
                else:
                    existing = entity_index[tid]
                    if session_number and session_number not in existing.source_sessions:
                        existing.source_sessions.append(session_number)

                new_relationships.append(Relationship(
                    source_id=source_id,
                    target_id=tid,
                    type="COVERS_TOPIC",
                    description=f"Keyword '{keyword}' (score={score:.2f})",
                    properties={"source": "keybert", "score": round(score, 3)},
                ))

        # KeyBERT on session summaries
        for session_dict in sessions_data:
            session_number = session_dict["session_number"]
            summary_text = session_dict.get("summary_text", "")
            session_id = f"session_{session_number}"
            _extract_topics(summary_text, session_id, session_number)

        # KeyBERT on presentation transcripts (richer source than summaries)
        if presentations_data:
            for pres in presentations_data:
                pres_id = pres.get("id", "")
                # Use transcript if available, fall back to summary
                text = pres.get("transcript", "") or pres.get("summary", "")
                if not text:
                    continue

                session_id = pres.get("session_id", "")
                session_number = None
                if session_id.startswith("session_"):
                    try:
                        session_number = int(session_id.split("_")[1])
                    except (IndexError, ValueError):
                        pass

                # More keywords for longer transcripts
                top_n = 8 if len(text) > 500 else 5
                _extract_topics(text, pres_id, session_number, top_n=top_n)

            logger.info(
                "KeyBERT processed %d presentations",
                len(presentations_data),
            )

        logger.info("KeyBERT enrichment complete, total new entities: %d", len(new_entities))

    except ImportError:
        logger.warning("KeyBERT not available, skipping keyword extraction")

    enriched_entities = entities + new_entities
    enriched_relationships = relationships + new_relationships
    return enriched_entities, enriched_relationships


def enrich(
    sessions_data: list[dict],
    extraction_result: ExtractionResult,
    presentations_data: list[dict] | None = None,
) -> ExtractionResult:
    """Convenience wrapper that takes and returns an ExtractionResult."""
    entities, relationships = enrich_graph(
        sessions_data,
        extraction_result.entities,
        extraction_result.relationships,
        presentations_data=presentations_data,
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
