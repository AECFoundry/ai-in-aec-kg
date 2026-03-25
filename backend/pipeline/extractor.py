"""LLM-based entity and relationship extraction from session summaries."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from openai import OpenAI

from pipeline.parser import SessionChunk

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are an expert knowledge graph builder for the architecture, engineering, \
and construction (AEC) industry. Extract entities and relationships from this \
conference session summary.

Session: {title}
Text: {summary_text}
Speakers present: {speaker_names}

Extract:
1. ENTITIES: People, organizations, technologies/tools, projects, \
concepts/methods mentioned.
   For each entity: {{"name": "...", "type": "Speaker|Organization|Technology|\
Project|Concept|Topic", "description": "one sentence"}}

2. RELATIONSHIPS: How entities relate to each other.
   For each: {{"source": "entity name", "target": "entity name", \
"type": "SPOKE_AT|AFFILIATED_WITH|COVERS_TOPIC|DISCUSSED|PRESENTED|\
RELATES_TO|USED_BY|MENTIONS_TECHNOLOGY|USES_TECHNOLOGY|LED_BY|\
PARTNERED_WITH|SUBTOPIC_OF", "description": "optional context"}}

3. TOPICS: High-level themes covered.
   For each: {{"name": "...", "description": "one sentence"}}

Return JSON: {{"entities": [...], "relationships": [...], "topics": [...]}}
"""


def _slugify(text: str) -> str:
    """Convert a string to a slug suitable for use as an ID."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    text = re.sub(r"-+", "_", text)
    return text.strip("_")


@dataclass
class Entity:
    id: str
    name: str
    type: str
    description: str
    source_sessions: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Entity:
        return cls(**d)


@dataclass
class Relationship:
    source_id: str
    target_id: str
    type: str
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Relationship:
        return cls(**d)


@dataclass
class ExtractionResult:
    entities: list[Entity]
    relationships: list[Relationship]

    def to_dict(self) -> dict:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExtractionResult:
        return cls(
            entities=[Entity.from_dict(e) for e in d["entities"]],
            relationships=[Relationship.from_dict(r) for r in d["relationships"]],
        )


def _make_entity_id(entity_type: str, name: str) -> str:
    """Generate a deterministic ID for an entity."""
    prefix = _slugify(entity_type)
    slug = _slugify(name)
    return f"{prefix}_{slug}"


def _make_session_id(session_number: int) -> str:
    return f"session_{session_number}"


def _extract_session(
    client: OpenAI,
    session: SessionChunk,
    *,
    model: str = "google/gemini-2.5-flash",
    max_retries: int = 2,
) -> dict:
    """Send a session summary to the LLM for entity/relationship extraction."""
    speaker_names = ", ".join(
        f"{s.name} ({s.organization})" for s in session.speakers
    ) or "Unknown"

    prompt = EXTRACTION_PROMPT.format(
        title=session.title,
        summary_text=session.summary_text[:4000],  # Trim to fit context
        speaker_names=speaker_names,
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            # Validate expected keys
            if "entities" not in data:
                data["entities"] = []
            if "relationships" not in data:
                data["relationships"] = []
            if "topics" not in data:
                data["topics"] = []
            return data
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning(
                "Extraction attempt %d failed for session %d: %s",
                attempt + 1,
                session.session_number,
                exc,
            )
            if attempt == max_retries:
                logger.error(
                    "All extraction attempts failed for session %d, returning empty",
                    session.session_number,
                )
                return {"entities": [], "relationships": [], "topics": []}
    return {"entities": [], "relationships": [], "topics": []}


def _build_structural_nodes(
    sessions: list[SessionChunk],
) -> tuple[list[Entity], list[Relationship]]:
    """Create Session and Speaker entities directly from parsed data (not LLM)."""
    entities: list[Entity] = []
    relationships: list[Relationship] = []
    seen_speaker_ids: set[str] = set()

    for session in sessions:
        session_id = _make_session_id(session.session_number)
        entities.append(Entity(
            id=session_id,
            name=session.title,
            type="Session",
            description=session.summary_text[:200] if session.summary_text else session.title,
            source_sessions=[session.session_number],
        ))

        for speaker in session.speakers:
            speaker_id = _make_entity_id("speaker", speaker.name)
            if speaker_id not in seen_speaker_ids:
                seen_speaker_ids.add(speaker_id)
                entities.append(Entity(
                    id=speaker_id,
                    name=speaker.name,
                    type="Speaker",
                    description=f"{speaker.name}, {speaker.title} at {speaker.organization}",
                    source_sessions=[session.session_number],
                ))
            else:
                # Update source_sessions for existing speaker
                for e in entities:
                    if e.id == speaker_id:
                        if session.session_number not in e.source_sessions:
                            e.source_sessions.append(session.session_number)
                        break

            # Speaker SPOKE_AT Session
            relationships.append(Relationship(
                source_id=speaker_id,
                target_id=session_id,
                type="SPOKE_AT",
                description=f"{speaker.name} spoke at {session.title}",
            ))

            # Speaker AFFILIATED_WITH Organization
            if speaker.organization and speaker.organization != "-":
                org_id = _make_entity_id("organization", speaker.organization)
                # Ensure org entity exists
                if not any(e.id == org_id for e in entities):
                    entities.append(Entity(
                        id=org_id,
                        name=speaker.organization,
                        type="Organization",
                        description=speaker.organization,
                        source_sessions=[session.session_number],
                    ))
                relationships.append(Relationship(
                    source_id=speaker_id,
                    target_id=org_id,
                    type="AFFILIATED_WITH",
                    description=f"{speaker.name} is affiliated with {speaker.organization}",
                ))

    return entities, relationships


def extract_all(
    sessions: list[SessionChunk],
    client: OpenAI,
    *,
    model: str = "google/gemini-2.5-flash",
) -> ExtractionResult:
    """Run extraction across all sessions and merge results."""
    # Build structural entities from parsed data
    entities, relationships = _build_structural_nodes(sessions)
    entity_index: dict[str, Entity] = {e.id: e for e in entities}

    for session in sessions:
        if not session.summary_text:
            logger.info(
                "Skipping LLM extraction for session %d (no summary)",
                session.session_number,
            )
            continue

        logger.info(
            "Extracting entities from session %d: %s",
            session.session_number,
            session.title,
        )
        data = _extract_session(client, session, model=model)

        # Process LLM-extracted entities
        for raw_entity in data.get("entities", []):
            name = raw_entity.get("name", "").strip()
            etype = raw_entity.get("type", "Concept").strip()
            description = raw_entity.get("description", "").strip()
            if not name:
                continue

            eid = _make_entity_id(etype, name)

            if eid in entity_index:
                # Merge: append to source_sessions, extend description if useful
                existing = entity_index[eid]
                if session.session_number not in existing.source_sessions:
                    existing.source_sessions.append(session.session_number)
                if description and len(description) > len(existing.description):
                    existing.description = description
            else:
                entity = Entity(
                    id=eid,
                    name=name,
                    type=etype,
                    description=description,
                    source_sessions=[session.session_number],
                )
                entity_index[eid] = entity
                entities.append(entity)

        # Process LLM-extracted topics
        for raw_topic in data.get("topics", []):
            tname = raw_topic.get("name", "").strip()
            tdesc = raw_topic.get("description", "").strip()
            if not tname:
                continue
            tid = _make_entity_id("topic", tname)
            if tid not in entity_index:
                topic_entity = Entity(
                    id=tid,
                    name=tname,
                    type="Topic",
                    description=tdesc,
                    source_sessions=[session.session_number],
                )
                entity_index[tid] = topic_entity
                entities.append(topic_entity)
            else:
                existing = entity_index[tid]
                if session.session_number not in existing.source_sessions:
                    existing.source_sessions.append(session.session_number)

            # Session COVERS_TOPIC
            session_id = _make_session_id(session.session_number)
            relationships.append(Relationship(
                source_id=session_id,
                target_id=tid,
                type="COVERS_TOPIC",
                description=f"{session.title} covers {tname}",
            ))

        # Process LLM-extracted relationships
        for raw_rel in data.get("relationships", []):
            source_name = raw_rel.get("source", "").strip()
            target_name = raw_rel.get("target", "").strip()
            rel_type = raw_rel.get("type", "RELATES_TO").strip()
            rel_desc = raw_rel.get("description", "").strip()

            if not source_name or not target_name:
                continue

            # Try to find matching entity IDs
            source_id = _find_entity_id(source_name, entity_index)
            target_id = _find_entity_id(target_name, entity_index)

            if source_id and target_id:
                # Sanitize relationship type for Neo4j (only alphanum and underscore)
                clean_type = re.sub(r"[^A-Z0-9_]", "_", rel_type.upper())
                relationships.append(Relationship(
                    source_id=source_id,
                    target_id=target_id,
                    type=clean_type,
                    description=rel_desc,
                    properties={"session": session.session_number},
                ))

    return ExtractionResult(entities=entities, relationships=relationships)


def _find_entity_id(name: str, entity_index: dict[str, Entity]) -> str | None:
    """Find the entity ID for a given name, trying multiple type prefixes."""
    name_slug = _slugify(name)
    # Try common type prefixes
    for prefix in [
        "speaker", "organization", "technology", "project",
        "concept", "topic", "session",
    ]:
        candidate = f"{prefix}_{name_slug}"
        if candidate in entity_index:
            return candidate
    # Try direct slug match against all IDs
    for eid in entity_index:
        if eid.endswith(f"_{name_slug}"):
            return eid
    return None


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")

    import os

    from pipeline.parser import parse_transcripts

    source = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parents[2] / "AI_in_AEC_2026_Snapsight_Summaries.txt"
    )

    logging.basicConfig(level=logging.INFO)
    sessions = parse_transcripts(source)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

    result = extract_all(sessions, client)
    print(f"Extracted {len(result.entities)} entities, {len(result.relationships)} relationships")

    out = Path(__file__).resolve().parents[1] / "data" / "pipeline_cache" / "extract_output.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    print(f"Wrote {out}")
