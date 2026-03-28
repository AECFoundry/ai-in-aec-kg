from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)


async def check_connectivity(driver: AsyncDriver) -> bool:
    """Return True if Neo4j is reachable."""
    try:
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS n")
            record = await result.single()
            return record is not None and record["n"] == 1
    except Exception:
        logger.exception("Neo4j connectivity check failed")
        return False


async def get_full_graph(driver: AsyncDriver) -> dict[str, list[dict]]:
    """Fetch all nodes and relationships from the knowledge graph."""
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    async with driver.session() as session:
        # Nodes
        result = await session.run(
            """
            MATCH (n)
            WHERE n:Session OR n:Speaker OR n:Organization OR n:Topic
                  OR n:Technology OR n:Concept OR n:Project OR n:Presentation
            RETURN n.id AS id, labels(n)[0] AS label, n.name AS name,
                   properties(n) AS props
            """
        )
        records = await result.data()
        for rec in records:
            props = dict(rec.get("props") or {})
            # Strip large fields — too heavy for the frontend
            props.pop("embedding", None)
            props.pop("transcript", None)
            props.pop("summary_text", None)
            props.pop("content", None)
            nodes.append(
                {
                    "id": rec["id"],
                    "label": rec["label"],
                    "name": rec["name"] or "",
                    "properties": props,
                }
            )

        # Relationships — only between nodes we've already selected
        node_ids = {n["id"] for n in nodes}
        result = await session.run(
            """
            MATCH (a)-[r]->(b)
            WHERE (a:Session OR a:Speaker OR a:Organization OR a:Topic
                   OR a:Technology OR a:Concept OR a:Project OR a:Presentation)
              AND (b:Session OR b:Speaker OR b:Organization OR b:Topic
                   OR b:Technology OR b:Concept OR b:Project OR b:Presentation)
            RETURN a.id AS source, b.id AS target, type(r) AS type,
                   properties(r) AS props
            """
        )
        records = await result.data()
        for rec in records:
            links.append(
                {
                    "source": rec["source"],
                    "target": rec["target"],
                    "type": rec["type"],
                    "properties": dict(rec.get("props") or {}),
                }
            )

    return {"nodes": nodes, "links": links}


async def vector_search(
    driver: AsyncDriver,
    index_name: str,
    embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """Query a single Neo4j vector index and return scored results."""
    try:
        async with driver.session() as session:
            result = await session.run(
                """
                CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
                YIELD node, score
                RETURN node.id AS id, node.name AS name, labels(node)[0] AS label,
                       coalesce(node.summary, node.description, node.content, '') AS context, score
                """,
                index_name=index_name,
                top_k=top_k,
                embedding=embedding,
            )
            return await result.data()
    except Exception:
        logger.warning("Vector search failed for index %s", index_name, exc_info=True)
        return []


async def expand_nodes(
    driver: AsyncDriver,
    node_ids: list[str],
    hops: int = 2,
) -> dict[str, list[dict]]:
    """Expand a set of seed node IDs by 1..hops hops and return nodes + links."""
    if not node_ids:
        return {"nodes": [], "links": []}

    async with driver.session() as session:
        result = await session.run(
            """
            MATCH path = (seed)-[*1..2]-(connected)
            WHERE seed.id IN $seed_ids
            WITH collect(DISTINCT connected) AS nodes,
                 collect(DISTINCT relationships(path)) AS rels_list
            UNWIND nodes AS n
            WITH collect(DISTINCT {id: n.id, name: n.name, label: labels(n)[0]}) AS expanded_nodes,
                 rels_list
            UNWIND rels_list AS rels
            UNWIND rels AS r
            WITH expanded_nodes,
                 collect(DISTINCT {
                     source: startNode(r).id,
                     target: endNode(r).id,
                     type: type(r)
                 }) AS expanded_links
            RETURN expanded_nodes, expanded_links
            """,
            seed_ids=node_ids,
        )
        record = await result.single()

    if record is None:
        return {"nodes": [], "links": []}

    return {
        "nodes": record["expanded_nodes"],
        "links": record["expanded_links"],
    }
