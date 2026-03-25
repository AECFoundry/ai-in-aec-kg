"""Neo4j schema creation — constraints and vector indexes."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SCHEMA_QUERIES = [
    "CREATE CONSTRAINT session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT speaker_id IF NOT EXISTS FOR (sp:Speaker) REQUIRE sp.id IS UNIQUE",
    "CREATE CONSTRAINT org_id IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT tech_id IF NOT EXISTS FOR (tech:Technology) REQUIRE tech.id IS UNIQUE",
    "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
]

VECTOR_INDEX_QUERIES = [
    """CREATE VECTOR INDEX session_embedding IF NOT EXISTS
       FOR (s:Session) ON (s.embedding)
      OPTIONS {indexConfig: {`vector.dimensions`: 3072, `vector.similarity_function`: 'cosine'}}""",
    """CREATE VECTOR INDEX speaker_embedding IF NOT EXISTS
       FOR (sp:Speaker) ON (sp.embedding)
      OPTIONS {indexConfig: {`vector.dimensions`: 3072, `vector.similarity_function`: 'cosine'}}""",
    """CREATE VECTOR INDEX organization_embedding IF NOT EXISTS
       FOR (o:Organization) ON (o.embedding)
      OPTIONS {indexConfig: {`vector.dimensions`: 3072, `vector.similarity_function`: 'cosine'}}""",
    """CREATE VECTOR INDEX topic_embedding IF NOT EXISTS
       FOR (t:Topic) ON (t.embedding)
      OPTIONS {indexConfig: {`vector.dimensions`: 3072, `vector.similarity_function`: 'cosine'}}""",
    """CREATE VECTOR INDEX technology_embedding IF NOT EXISTS
       FOR (tech:Technology) ON (tech.embedding)
      OPTIONS {indexConfig: {`vector.dimensions`: 3072, `vector.similarity_function`: 'cosine'}}""",
    """CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
       FOR (c:Concept) ON (c.embedding)
      OPTIONS {indexConfig: {`vector.dimensions`: 3072, `vector.similarity_function`: 'cosine'}}""",
    """CREATE VECTOR INDEX project_embedding IF NOT EXISTS
       FOR (p:Project) ON (p.embedding)
      OPTIONS {indexConfig: {`vector.dimensions`: 3072, `vector.similarity_function`: 'cosine'}}""",
]


async def create_schema(neo4j_session) -> None:
    """Create all constraints and vector indexes in Neo4j."""
    for query in SCHEMA_QUERIES:
        try:
            await neo4j_session.run(query)
            logger.info("Created constraint: %s", query[:60])
        except Exception as exc:
            logger.warning("Constraint may already exist: %s", exc)

    for query in VECTOR_INDEX_QUERIES:
        try:
            await neo4j_session.run(query)
            logger.info("Created vector index: %s", query[:60])
        except Exception as exc:
            logger.warning("Vector index may already exist: %s", exc)


if __name__ == "__main__":
    import asyncio
    import os
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    logging.basicConfig(level=logging.INFO)

    import neo4j

    async def main():
        driver = neo4j.AsyncGraphDatabase.driver(
            os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.environ.get("NEO4J_USER", "neo4j"),
                os.environ.get("NEO4J_PASSWORD", ""),
            ),
        )
        async with driver.session() as session:
            await create_schema(session)
        await driver.close()
        print("Schema created successfully")

    asyncio.run(main())
