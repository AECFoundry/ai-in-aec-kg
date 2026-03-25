"""Deduplicate entities that refer to the same real-world thing using fuzzy matching."""

from __future__ import annotations

import logging
from collections import defaultdict

from rapidfuzz import fuzz

from pipeline.extractor import Entity, ExtractionResult, Relationship

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 85


def _normalize(name: str) -> str:
    """Normalize a name for comparison."""
    name = name.lower().strip()
    # Remove trailing punctuation
    name = name.rstrip(".,;:!?")
    return name


def _pick_canonical(a: Entity, b: Entity) -> tuple[Entity, Entity]:
    """Return (canonical, duplicate) — keep the longer/more complete name."""
    if len(a.name) >= len(b.name):
        return a, b
    return b, a


def _merge_entities(canonical: Entity, duplicate: Entity) -> Entity:
    """Merge duplicate into canonical, combining descriptions and source_sessions."""
    # Merge source sessions
    merged_sessions = list(set(canonical.source_sessions + duplicate.source_sessions))
    merged_sessions.sort()

    # Keep the longer description
    description = canonical.description
    if len(duplicate.description) > len(description):
        description = duplicate.description

    return Entity(
        id=canonical.id,
        name=canonical.name,
        type=canonical.type,
        description=description,
        source_sessions=merged_sessions,
    )


def resolve_entities(
    entities: list[Entity],
    relationships: list[Relationship],
    *,
    threshold: int = SIMILARITY_THRESHOLD,
) -> tuple[list[Entity], list[Relationship]]:
    """Deduplicate entities and update relationship references.

    Strategy:
    1. Normalize names: lowercase, strip whitespace, remove trailing punctuation
    2. Group by entity type
    3. Within each type, use rapidfuzz token_sort_ratio to find pairs > threshold
    4. For matched pairs: keep longer/more complete name as canonical, merge descriptions
    5. Update all relationships to use canonical names
    """
    # Group entities by type
    by_type: dict[str, list[Entity]] = defaultdict(list)
    for entity in entities:
        by_type[entity.type].append(entity)

    # Build mapping: old_id -> canonical_id
    id_mapping: dict[str, str] = {}
    merged_away: set[str] = set()

    for entity_type, type_entities in by_type.items():
        n = len(type_entities)
        if n < 2:
            continue

        # Find similar pairs
        for i in range(n):
            if type_entities[i].id in merged_away:
                continue
            for j in range(i + 1, n):
                if type_entities[j].id in merged_away:
                    continue

                name_a = _normalize(type_entities[i].name)
                name_b = _normalize(type_entities[j].name)

                score = fuzz.token_sort_ratio(name_a, name_b)
                if score >= threshold:
                    canonical, duplicate = _pick_canonical(
                        type_entities[i], type_entities[j]
                    )
                    logger.info(
                        "Merging '%s' into '%s' (score=%d, type=%s)",
                        duplicate.name,
                        canonical.name,
                        score,
                        entity_type,
                    )
                    # Record the mapping
                    id_mapping[duplicate.id] = canonical.id
                    merged_away.add(duplicate.id)

                    # Merge the entities in place
                    merged = _merge_entities(canonical, duplicate)
                    # Update the canonical entity in the list
                    idx = i if type_entities[i].id == canonical.id else j
                    type_entities[idx] = merged

    # Build the resolved entity list (exclude merged-away entities)
    resolved_entities = [e for e in entities if e.id not in merged_away]

    # For entities that were merged, update their data in the resolved list
    canonical_map: dict[str, Entity] = {}
    for entity_type, type_entities in by_type.items():
        for e in type_entities:
            if e.id not in merged_away:
                canonical_map[e.id] = e

    resolved_entities = list(canonical_map.values())

    # Update relationships to use canonical IDs
    updated_relationships: list[Relationship] = []
    seen_rels: set[tuple[str, str, str]] = set()

    for rel in relationships:
        source_id = id_mapping.get(rel.source_id, rel.source_id)
        target_id = id_mapping.get(rel.target_id, rel.target_id)

        # Skip self-relationships created by merging
        if source_id == target_id:
            continue

        # Deduplicate relationships
        rel_key = (source_id, target_id, rel.type)
        if rel_key in seen_rels:
            continue
        seen_rels.add(rel_key)

        updated_relationships.append(Relationship(
            source_id=source_id,
            target_id=target_id,
            type=rel.type,
            description=rel.description,
            properties=rel.properties,
        ))

    logger.info(
        "Resolution: %d entities -> %d entities, %d relationships -> %d relationships",
        len(entities),
        len(resolved_entities),
        len(relationships),
        len(updated_relationships),
    )

    return resolved_entities, updated_relationships


def resolve(extraction_result: ExtractionResult) -> ExtractionResult:
    """Convenience wrapper that takes and returns an ExtractionResult."""
    entities, relationships = resolve_entities(
        extraction_result.entities, extraction_result.relationships
    )
    return ExtractionResult(entities=entities, relationships=relationships)


if __name__ == "__main__":
    import json
    from pathlib import Path

    logging.basicConfig(level=logging.INFO)

    cache_dir = Path(__file__).resolve().parents[1] / "data" / "pipeline_cache"
    extract_path = cache_dir / "extract_output.json"

    if not extract_path.exists():
        print(f"No extraction output found at {extract_path}. Run extractor first.")
        raise SystemExit(1)

    data = json.loads(extract_path.read_text(encoding="utf-8"))
    extraction = ExtractionResult.from_dict(data)

    result = resolve(extraction)
    print(
        f"Resolved: {len(result.entities)} entities, "
        f"{len(result.relationships)} relationships"
    )

    out = cache_dir / "resolve_output.json"
    out.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    print(f"Wrote {out}")
