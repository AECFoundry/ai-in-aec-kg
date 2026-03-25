from __future__ import annotations

import json
import logging
import re
from typing import Any

from neo4j import AsyncDriver
from openai import AsyncOpenAI

from app.models.schemas import ChatMessage
from app.services.embeddings import embed_text
from app.services.neo4j_queries import expand_nodes, vector_search

logger = logging.getLogger(__name__)

# Known vector index names — one per node label that has embeddings.
_VECTOR_INDEXES = [
    "session_embedding",
    "speaker_embedding",
    "organization_embedding",
    "topic_embedding",
    "technology_embedding",
    "concept_embedding",
    "project_embedding",
]


async def _discover_vector_indexes(driver: AsyncDriver) -> list[str]:
    """Return the subset of expected indexes that actually exist in Neo4j."""
    try:
        async with driver.session() as session:
            result = await session.run("SHOW INDEXES YIELD name RETURN name")
            records = await result.data()
            existing = {r["name"] for r in records}
        return [idx for idx in _VECTOR_INDEXES if idx in existing]
    except Exception:
        logger.warning("Could not discover vector indexes", exc_info=True)
        return []


async def query_graph(
    question: str,
    neo4j_driver: AsyncDriver,
    openai_client: AsyncOpenAI,
    chat_history: list[ChatMessage] | None = None,
) -> dict[str, Any]:
    """
    6-step GraphRAG pipeline.

    Returns dict with keys: answer, subgraph, sources.
    """

    # ------------------------------------------------------------------
    # Step 1 — Embed the user question
    # ------------------------------------------------------------------
    embedding = await embed_text(question, openai_client)

    # ------------------------------------------------------------------
    # Step 2 — Semantic search across all vector indexes
    # ------------------------------------------------------------------
    indexes = await _discover_vector_indexes(neo4j_driver)
    all_candidates: list[dict] = []

    for idx in indexes:
        hits = await vector_search(neo4j_driver, idx, embedding, top_k=5)
        all_candidates.extend(hits)

    # Sort by score descending, take top 15
    all_candidates.sort(key=lambda c: c.get("score", 0), reverse=True)
    top_candidates = all_candidates[:15]

    if not top_candidates:
        return {
            "answer": "I could not find any relevant information in the knowledge graph.",
            "subgraph": {"node_ids": [], "link_ids": []},
            "sources": [],
        }

    # ------------------------------------------------------------------
    # Step 3 — Ask LLM to select the most relevant node IDs
    # ------------------------------------------------------------------
    candidates_text = json.dumps(
        [
            {"id": c["id"], "name": c["name"], "label": c["label"], "context": c["context"][:300]}
            for c in top_candidates
        ],
        indent=2,
    )

    selection_messages = [
        {
            "role": "system",
            "content": (
                "You are a knowledge-graph analyst. Given a user question and a list of "
                "candidate nodes from a knowledge graph about AI in AEC (Architecture, "
                "Engineering, Construction), select the IDs of the most relevant nodes. "
                "Return ONLY a JSON array of id strings, e.g. [\"id1\", \"id2\"]. "
                "Select between 1 and 8 nodes."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nCandidate nodes:\n{candidates_text}",
        },
    ]

    selection_resp = await openai_client.chat.completions.create(
        model="openai/gpt-4.1",
        messages=selection_messages,
        max_tokens=256,
        temperature=0,
    )
    raw_ids = selection_resp.choices[0].message.content or "[]"

    try:
        selected_ids = json.loads(raw_ids)
        if not isinstance(selected_ids, list):
            selected_ids = []
        selected_ids = [str(sid) for sid in selected_ids]
    except json.JSONDecodeError:
        # Try to extract JSON array from the response
        match = re.search(r"\[.*?\]", raw_ids, re.DOTALL)
        if match:
            try:
                selected_ids = json.loads(match.group())
                selected_ids = [str(sid) for sid in selected_ids]
            except json.JSONDecodeError:
                selected_ids = [c["id"] for c in top_candidates[:5]]
        else:
            selected_ids = [c["id"] for c in top_candidates[:5]]

    if not selected_ids:
        selected_ids = [c["id"] for c in top_candidates[:5]]

    # ------------------------------------------------------------------
    # Step 4 — Expand selected nodes 2 hops
    # ------------------------------------------------------------------
    expanded = await expand_nodes(neo4j_driver, selected_ids, hops=2)
    expanded_nodes = expanded.get("nodes", [])
    expanded_links = expanded.get("links", [])

    # ------------------------------------------------------------------
    # Step 5 — Generate answer from subgraph context
    # ------------------------------------------------------------------
    # Build context text from candidates + expanded subgraph
    context_parts: list[str] = []
    for c in top_candidates:
        if c["id"] in selected_ids:
            context_parts.append(
                f"[{c['label']}] (id={c['id']}) {c['name']}: {c.get('context', '')}"
            )

    subgraph_desc_parts: list[str] = []
    for n in expanded_nodes:
        subgraph_desc_parts.append(
            f"  Node: (id={n.get('id', '')}) {n.get('name', '')} ({n.get('label', '')})"
        )
    for link in expanded_links:
        subgraph_desc_parts.append(
            f"  Link: {link.get('source', '')} "
            f"-[{link.get('type', '')}]-> {link.get('target', '')}"
        )

    context_text = "\n".join(context_parts)
    subgraph_text = "\n".join(subgraph_desc_parts[:60])  # limit context size

    # Build conversation history for context
    history_messages: list[dict[str, str]] = []
    if chat_history:
        for msg in chat_history[-6:]:  # last 6 messages for context
            history_messages.append({"role": msg.role, "content": msg.content})

    answer_messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are an expert assistant for the AI in AEC (Architecture, Engineering, "
                "Construction) knowledge graph. Answer the user's question using ONLY the "
                "provided context from the knowledge graph. Be specific and cite the relevant "
                "sessions, speakers, organizations, or technologies. If the context does not "
                "contain enough information, say so.\n\n"
                "After your answer, provide a JSON block on a new line starting with "
                "```json and ending with ``` containing:\n"
                '{"relevant_node_ids": ["id1", ...],'
                ' "relevant_links": ["source_id->target_id", ...]}\n'
                "IMPORTANT: Use the actual node id values "
                "(shown as id=xxx in the context), "
                "NOT the node names. Only include nodes and "
                "links that directly support your answer."
            ),
        },
        *history_messages,
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"--- Relevant nodes ---\n{context_text}\n\n"
                f"--- Subgraph neighbourhood ---\n{subgraph_text}"
            ),
        },
    ]

    answer_resp = await openai_client.chat.completions.create(
        model="openai/gpt-4.1",
        messages=answer_messages,
        max_tokens=1024,
        temperature=0.2,
    )
    full_answer = answer_resp.choices[0].message.content or ""

    # ------------------------------------------------------------------
    # Step 6 — Parse answer and subgraph highlight
    # ------------------------------------------------------------------
    answer_text = full_answer
    highlight_node_ids: list[str] = list(selected_ids)
    highlight_link_ids: list[str] = []

    # Try to extract the JSON block
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", full_answer, re.DOTALL)
    if json_match:
        answer_text = full_answer[: json_match.start()].strip()
        try:
            highlight_data = json.loads(json_match.group(1))
            if "relevant_node_ids" in highlight_data:
                llm_ids = [str(nid) for nid in highlight_data["relevant_node_ids"]]
                # Only use LLM IDs if they look like real IDs (contain underscores)
                # and intersect with known candidate IDs
                candidate_id_set = {c["id"] for c in top_candidates}
                valid_llm_ids = [nid for nid in llm_ids if nid in candidate_id_set]
                if valid_llm_ids:
                    highlight_node_ids = valid_llm_ids
            if "relevant_links" in highlight_data:
                highlight_link_ids = highlight_data["relevant_links"]
        except json.JSONDecodeError:
            pass

    # Always include selected_ids in highlights (they're reliable)
    all_highlight_ids = set(highlight_node_ids) | set(selected_ids)

    # Build sources from the selected candidates
    sources = [
        {
            "id": c["id"],
            "name": c["name"],
            "label": c["label"],
            "score": round(c.get("score", 0), 4),
        }
        for c in top_candidates
        if c["id"] in all_highlight_ids
    ]

    return {
        "answer": answer_text,
        "subgraph": {
            "node_ids": list(all_highlight_ids),
            "link_ids": highlight_link_ids,
        },
        "sources": sources,
    }
