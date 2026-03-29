"""LangGraph agent tools for knowledge graph exploration."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.config import get_stream_writer

from app.services.embeddings import embed_text
from app.services.neo4j_queries import expand_nodes, vector_search

logger = logging.getLogger(__name__)

_TYPE_TO_INDEX = {
    "Session": "session_embedding",
    "Speaker": "speaker_embedding",
    "Organization": "organization_embedding",
    "Topic": "topic_embedding",
    "Technology": "technology_embedding",
    "Concept": "concept_embedding",
    "Project": "project_embedding",
    "Presentation": "presentation_embedding",
    "TranscriptChunk": "chunk_embedding",
}

_VALID_LABELS_LIST = [
    "Session", "Speaker", "Organization", "Topic",
    "Technology", "Concept", "Project", "Presentation",
    "TranscriptChunk",
]


@tool
async def vector_search_nodes(
    query: str,
    node_types: list[str],
    top_k: int = 5,
    *,
    config: RunnableConfig,
) -> str:
    """Search the knowledge graph for nodes semantically similar to a query.

    Args:
        query: The search text to embed and match against.
        node_types: Which node types to search. Valid types:
            Session, Speaker, Organization, Topic, Technology,
            Concept, Project, Presentation, TranscriptChunk.
            Choose types relevant to the question — usually 2-4 types.
            Use TranscriptChunk for specific quotes or technical details.
        top_k: Number of results per type (default 5, max 10).
    """
    writer = get_stream_writer()
    driver = config["configurable"]["neo4j_driver"]
    openai_client = config["configurable"]["openai_client"]

    type_names = ", ".join(node_types)
    writer({"type": "tool_progress", "tool": "vector_search",
            "detail": f"Searching {type_names} for: \"{query[:80]}\""})

    embedding = await embed_text(query, openai_client)

    all_hits: list[dict[str, Any]] = []
    for nt in node_types:
        idx = _TYPE_TO_INDEX.get(nt)
        if not idx:
            continue
        hits = await vector_search(driver, idx, embedding, top_k=min(top_k, 10))
        all_hits.extend(hits)

    all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
    top = all_hits[:10]

    writer({"type": "tool_result", "tool": "vector_search",
            "detail": f"Found {len(top)} relevant nodes"})

    if not top:
        return "No results found."

    lines = []
    for h in top:
        ctx = (h.get("context") or "")[:120]
        lines.append(
            f"- [{h['label']}] {h['name']} (id={h['id']}, score={h['score']:.3f}): {ctx}"
        )
    return "\n".join(lines)


@tool
async def get_node_neighbors(
    node_id: str,
    relationship_types: list[str] | None = None,
    *,
    config: RunnableConfig,
) -> str:
    """Get immediate neighbors of a node in the knowledge graph.

    Args:
        node_id: The ID of the node to explore.
        relationship_types: Optional filter for relationship types.
            Examples: SPOKE_AT, AFFILIATED_WITH, COVERS_TOPIC, DISCUSSED,
            PRESENTED, RELATES_TO, USED_BY, MENTIONS_TECHNOLOGY,
            USES_TECHNOLOGY, PART_OF, PRESENTED_BY, MENTIONS.
            If omitted, returns all neighbors.
    """
    writer = get_stream_writer()
    driver = config["configurable"]["neo4j_driver"]

    writer({"type": "tool_progress", "tool": "get_neighbors",
            "detail": f"Exploring connections of {node_id}"})

    rel_filter = ""
    params: dict[str, Any] = {"node_id": node_id}
    if relationship_types:
        rel_filter = "AND type(r) IN $rel_types"
        params["rel_types"] = relationship_types

    label_filter = " OR ".join(f"neighbor:{l}" for l in _VALID_LABELS_LIST)
    query = f"""
    MATCH (n {{id: $node_id}})-[r]-(neighbor)
    WHERE ({label_filter})
    {rel_filter}
    RETURN neighbor.id AS id, neighbor.name AS name, labels(neighbor)[0] AS label,
           type(r) AS rel_type, startNode(r).id AS source, endNode(r).id AS target,
           coalesce(neighbor.summary, neighbor.description, '') AS context
    LIMIT 30
    """

    async with driver.session() as session:
        result = await session.run(query, **params)
        records = await result.data()

    writer({"type": "tool_result", "tool": "get_neighbors",
            "detail": f"Found {len(records)} connections"})

    if not records:
        return f"Node {node_id} has no connections matching the criteria."

    lines = []
    for r in records:
        direction = "->" if r["source"] == node_id else "<-"
        ctx = (r.get("context") or "")[:120]
        lines.append(
            f"- [{r['label']}] {r['name']} (id={r['id']}) "
            f"[{direction} {r['rel_type']}]: {ctx}"
        )
    return "\n".join(lines)


@tool
async def find_paths(
    source_id: str,
    target_id: str,
    max_hops: int = 3,
    *,
    config: RunnableConfig,
) -> str:
    """Find shortest paths between two nodes in the knowledge graph.

    Args:
        source_id: Starting node ID.
        target_id: Ending node ID.
        max_hops: Maximum path length (default 3, max 4).
    """
    writer = get_stream_writer()
    driver = config["configurable"]["neo4j_driver"]

    writer({"type": "tool_progress", "tool": "find_paths",
            "detail": f"Finding paths between {source_id} and {target_id}"})

    hops = min(max_hops, 4)
    query = f"""
    MATCH path = shortestPath((a {{id: $source}})-[*1..{hops}]-(b {{id: $target}}))
    RETURN [n IN nodes(path) | {{id: n.id, name: n.name, label: labels(n)[0]}}] AS nodes,
           [r IN relationships(path) | {{type: type(r), source: startNode(r).id, target: endNode(r).id}}] AS rels
    LIMIT 3
    """

    async with driver.session() as session:
        result = await session.run(query, source=source_id, target=target_id)
        records = await result.data()

    if not records:
        writer({"type": "tool_result", "tool": "find_paths",
                "detail": "No paths found"})
        return f"No path found between {source_id} and {target_id} within {hops} hops."

    writer({"type": "tool_result", "tool": "find_paths",
            "detail": f"Found {len(records)} path(s)"})

    lines = []
    for i, rec in enumerate(records):
        path_nodes = rec["nodes"]
        path_str = " -> ".join(f"{n['name']}({n['label']})" for n in path_nodes)
        lines.append(f"Path {i + 1}: {path_str}")
        for r in rec["rels"]:
            lines.append(f"  {r['source']} -[{r['type']}]-> {r['target']}")
    return "\n".join(lines)


@tool
async def expand_subgraph(
    node_ids: list[str],
    hops: int = 1,
    *,
    config: RunnableConfig,
) -> str:
    """Expand a set of nodes by N hops to discover their neighborhood.

    Use after identifying seed nodes to understand broader context.

    Args:
        node_ids: List of node IDs to expand from (1-8 recommended).
        hops: How many hops to expand (1 or 2, default 1).
    """
    writer = get_stream_writer()
    driver = config["configurable"]["neo4j_driver"]

    writer({"type": "tool_progress", "tool": "expand_subgraph",
            "detail": f"Expanding {len(node_ids)} nodes by {hops} hop(s)"})

    expanded = await expand_nodes(driver, node_ids, hops=min(hops, 2))
    exp_nodes = expanded.get("nodes", [])
    exp_links = expanded.get("links", [])

    writer({"type": "tool_result", "tool": "expand_subgraph",
            "detail": f"Expanded to {len(exp_nodes)} nodes, {len(exp_links)} relationships"})

    lines = ["Nodes in subgraph:"]
    for n in exp_nodes[:40]:
        lines.append(f"  - [{n['label']}] {n['name']} (id={n['id']})")

    lines.append("\nRelationships:")
    for link in exp_links[:40]:
        lines.append(f"  - {link['source']} -[{link['type']}]-> {link['target']}")

    return "\n".join(lines)


@tool
async def get_node_details(
    node_id: str,
    *,
    config: RunnableConfig,
) -> str:
    """Get full details of a specific node by its ID.

    Args:
        node_id: The node ID to look up.
    """
    writer = get_stream_writer()
    driver = config["configurable"]["neo4j_driver"]

    writer({"type": "tool_progress", "tool": "get_node_details",
            "detail": f"Looking up {node_id}"})

    query = """
    MATCH (n {id: $node_id})
    RETURN labels(n)[0] AS label, n.name AS name, properties(n) AS props
    """
    async with driver.session() as session:
        result = await session.run(query, node_id=node_id)
        record = await result.single()

    if not record:
        writer({"type": "tool_result", "tool": "get_node_details",
                "detail": "Node not found"})
        return f"No node found with id={node_id}."

    props = dict(record["props"])
    label = record["label"]
    props.pop("embedding", None)  # too large

    writer({"type": "tool_result", "tool": "get_node_details",
            "detail": f"Found {label}: {record['name']}"})

    # Strip large text fields — but keep content for chunks and transcripts for presentations
    props.pop("summary_text", None)
    if label == "TranscriptChunk":
        # Keep full content (~2000 chars)
        pass
    elif label == "Presentation":
        # Include truncated transcript for context; agent can fetch full via Cypher
        transcript = props.pop("transcript", None)
        if transcript:
            props["transcript_preview"] = transcript[:1500] + (
                f"\n\n[... truncated — full transcript is {len(transcript)} chars. "
                "Use run_cypher_query with MATCH (p:Presentation {id: $id}) RETURN p.transcript to retrieve full text.]"
                if len(transcript) > 1500 else ""
            )
        props.pop("content", None)
    else:
        props.pop("transcript", None)
        props.pop("content", None)

    lines = [f"[{label}] {record['name']} (id={node_id})"]
    for k, v in props.items():
        if k in ("id", "name"):
            continue
        # Allow chunk content up to 2500 chars, truncate other strings at 200
        max_len = 2500 if k == "content" else 200
        val_str = str(v)[:max_len] if isinstance(v, str) else str(v)
        lines.append(f"  {k}: {val_str}")
    return "\n".join(lines)


@tool
async def run_cypher_query(
    query: str,
    description: str,
    *,
    config: RunnableConfig,
) -> str:
    """Run a read-only Cypher query for quantitative or aggregation questions.

    Use this for counts, rankings, statistics, or structural queries that the
    other tools cannot answer (e.g. "how many speakers are there?",
    "which topic has the most connections?", "list all sessions").

    Args:
        query: A read-only Cypher query. ONLY MATCH/RETURN/WITH/ORDER BY/LIMIT
            are allowed — no CREATE/MERGE/DELETE/SET/REMOVE.
            Use node labels: Session, Speaker, Organization, Topic, Technology,
            Concept, Project, Presentation, TranscriptChunk.
            Relationship types: SPOKE_AT, AFFILIATED_WITH, COVERS_TOPIC,
            DISCUSSED, PRESENTED, RELATES_TO, USED_BY, MENTIONS_TECHNOLOGY,
            MENTIONS_PROJECT, USES_TECHNOLOGY, LED_BY, SUBTOPIC_OF, PART_OF,
            PRESENTED_BY, MENTIONS, CHUNK_OF.
        description: Brief explanation of what this query answers.
    """
    writer = get_stream_writer()
    driver = config["configurable"]["neo4j_driver"]

    writer({"type": "tool_progress", "tool": "cypher_query",
            "detail": f"Running query: {description}"})

    # Safety check: block write operations
    upper = query.upper().strip()
    forbidden = ["CREATE", "MERGE", "DELETE", "DETACH", "SET ", "REMOVE", "DROP", "CALL {"]
    for kw in forbidden:
        if kw in upper:
            return f"Refused: write operation '{kw.strip()}' not allowed."

    try:
        async with driver.session() as session:
            result = await session.run(query)
            records = await result.data()
    except Exception as exc:
        writer({"type": "tool_result", "tool": "cypher_query",
                "detail": f"Query failed: {exc}"})
        return f"Query error: {exc}"

    writer({"type": "tool_result", "tool": "cypher_query",
            "detail": f"Returned {len(records)} row(s)"})

    if not records:
        return "Query returned no results."

    # Format results as text table
    lines = []
    keys = list(records[0].keys())
    lines.append(" | ".join(keys))
    lines.append("-" * len(lines[0]))
    for rec in records[:50]:
        vals = [str(rec.get(k, ""))[:100] for k in keys]
        lines.append(" | ".join(vals))

    if len(records) > 50:
        lines.append(f"... ({len(records) - 50} more rows)")

    return "\n".join(lines)


ALL_TOOLS = [
    vector_search_nodes,
    get_node_neighbors,
    find_paths,
    expand_subgraph,
    get_node_details,
    run_cypher_query,
]
