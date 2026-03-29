"""LangGraph agentic GraphRAG pipeline."""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.services.agent_llm import get_agent_llm
from app.services.agent_state import AgentState
from app.services.agent_tools import ALL_TOOLS

logger = logging.getLogger(__name__)

TOOL_MAP = {t.name: t for t in ALL_TOOLS}

SYSTEM_PROMPT = """\
You are an expert assistant for the AI in AEC (Architecture, Engineering, Construction) \
2026 conference knowledge graph. You answer questions by exploring a Neo4j knowledge graph \
containing ~1700 nodes and ~2500 edges from the Helsinki conference.

**Node types:** Session, Speaker, Organization, Topic, Technology, Concept, Project, Presentation, TranscriptChunk
**Relationships:** SPOKE_AT, AFFILIATED_WITH, COVERS_TOPIC, DISCUSSED, PRESENTED, \
RELATES_TO, USED_BY, MENTIONS_TECHNOLOGY, MENTIONS_PROJECT, USES_TECHNOLOGY, \
LED_BY, SUBTOPIC_OF, PART_OF, PRESENTED_BY, MENTIONS, CHUNK_OF

TranscriptChunk nodes contain ~400-word excerpts from formatted presentation transcripts. \
Search them for specific quotes, technical details, or granular content that may not appear \
in summaries. They link to their parent Presentation via CHUNK_OF. \
Presentation nodes store the full formatted transcript in their `transcript` property. \
get_node_details shows a 1500-char preview; use run_cypher_query to fetch the full text \
when you need comprehensive coverage of a presentation.

**Your approach:**
1. Start with vector_search_nodes to find semantically relevant nodes. **Always include \
TranscriptChunk** in your node_types — chunks contain the actual presentation content and \
are the richest source of detail. Add 1-2 other types relevant to the question (e.g. \
Presentation, Topic, Speaker). Don't search all 9 types — pick 2-4.
2. Use get_node_neighbors to explore specific nodes and understand their connections.
3. Use get_node_details for full information on key nodes.
4. Use expand_subgraph for broader context around important nodes.
5. Use find_paths to discover how two concepts are connected.
6. Use run_cypher_query for quantitative questions (counts, rankings, aggregations, \
listing all items of a type, etc.). Write read-only Cypher.

**Rules:**
- Be efficient: aim for 1-2 rounds of tool calls maximum, then produce your answer.
- Make targeted, parallel tool calls. Usually 1-3 calls per round suffice.
- In your final answer use numbered inline citations [1], [2], etc. Only cite \
**Presentations, Sessions, and Speakers** — these give users navigable context. \
When your evidence comes from a TranscriptChunk, Topic, Technology, Concept, or other node, \
trace back to the parent Presentation or Session and cite that instead. \
Number citations sequentially as you mention them.
- NEVER expose raw database IDs (like id=topic_bim) in your answer text. Use only [N] citations.
- Do NOT include a "References", "Sources", or bibliography section at the end of your answer. \
The UI automatically renders a clickable source list from the citation numbers — any trailing \
reference list you add is redundant. End your answer with your final prose sentence.
- Write clear, informative markdown prose.
- If context is insufficient, say so honestly."""


async def llm_call(state: AgentState) -> dict[str, Any]:
    """Invoke the LLM with tool-binding."""
    writer = get_stream_writer()
    llm = get_agent_llm().bind_tools(ALL_TOOLS)

    # Build messages: system + chat history + agent messages
    msgs: list[Any] = [SystemMessage(content=SYSTEM_PROMPT)]

    # Prior conversation turns as context
    for msg in (state.get("chat_history") or [])[-6:]:
        if msg["role"] == "user":
            msgs.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            msgs.append(AIMessage(content=msg["content"]))

    msgs.extend(state["messages"])

    writer({"type": "thinking", "detail": "Reasoning about the question..."})

    # Retry on empty responses (OpenRouter intermittently returns empty)
    response = None
    for attempt in range(3):
        response = await llm.ainvoke(msgs)
        if response.content or response.tool_calls:
            break
        logger.warning("llm_call: empty response on attempt %d, retrying...", attempt + 1)

    if response.tool_calls:
        for tc in response.tool_calls:
            writer({"type": "tool_call", "tool": tc["name"],
                    "detail": f"Using {tc['name']}"})

    return {"messages": [response]}


async def tool_node(state: AgentState) -> dict[str, Any]:
    """Execute tool calls and capture node IDs / sources."""
    writer = get_stream_writer()
    last_msg = state["messages"][-1]
    results: list[ToolMessage] = []
    new_node_ids: set[str] = set()
    new_link_ids: set[str] = set()
    new_sources: list[dict[str, Any]] = []

    for tc in last_msg.tool_calls:
        tool_fn = TOOL_MAP.get(tc["name"])
        if not tool_fn:
            results.append(ToolMessage(
                content=f"Unknown tool: {tc['name']}",
                tool_call_id=tc["id"],
            ))
            continue

        try:
            observation = await tool_fn.ainvoke(tc)
        except Exception:
            logger.exception("Tool %s failed", tc["name"])
            results.append(ToolMessage(
                content=f"Tool {tc['name']} failed. Try a different approach.",
                tool_call_id=tc["id"],
            ))
            continue

        # ainvoke with a ToolCall dict returns a ToolMessage; extract raw content
        if hasattr(observation, "content"):
            obs_text = observation.content if isinstance(observation.content, str) else str(observation.content)
        else:
            obs_text = str(observation)
        results.append(ToolMessage(content=obs_text, tool_call_id=tc["id"]))

        # Extract node IDs from tool output (filter out tool call IDs)
        found_ids = re.findall(r"id=([a-z][a-z0-9_]+)", obs_text)
        new_node_ids.update(found_ids)

        # Capture vector search results as citation sources
        if tc["name"] == "vector_search_nodes":
            for line in obs_text.split("\n"):
                m = re.match(
                    r"- \[(\w+)\] (.+?) \(id=([^,)]+), score=([\d.]+)\): (.*)",
                    line,
                )
                if m:
                    new_sources.append({
                        "label": m.group(1),
                        "name": m.group(2),
                        "id": m.group(3),
                        "score": float(m.group(4)),
                        "context": m.group(5),
                    })

        # Capture neighbors / details as potential citation sources
        if tc["name"] in ("get_node_neighbors", "get_node_details"):
            for line in obs_text.split("\n"):
                m = re.match(
                    r"(?:- )?\[(\w+)\] (.+?) \(id=([^,)]+)\)",
                    line,
                )
                if m:
                    new_sources.append({
                        "label": m.group(1),
                        "name": m.group(2),
                        "id": m.group(3),
                        "score": 0,
                        "context": "",
                    })

        # Capture link IDs from expand_subgraph
        if tc["name"] == "expand_subgraph":
            for src, tgt in re.findall(r"(\S+) -\[\w+\]-> (\S+)", obs_text):
                new_link_ids.add(f"{src}->{tgt}")

        # Stream discovered nodes to frontend for progressive graph highlighting
        if new_node_ids or new_link_ids:
            writer({
                "type": "graph_update",
                "node_ids": sorted(new_node_ids),
                "link_ids": sorted(new_link_ids),
            })

    return {
        "messages": results,
        "visited_node_ids": new_node_ids,
        "visited_link_ids": new_link_ids,
        "collected_sources": new_sources,
    }


async def finalize(state: AgentState) -> dict[str, Any]:
    """Build the final output contract from agent state."""
    writer = get_stream_writer()
    writer({"type": "thinking", "detail": "Preparing final answer..."})

    # Find the last AIMessage (skip ToolMessages at end of list)
    last_msg = state["messages"][-1]
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage):
            last_msg = msg
            break
    answer_text = last_msg.content if hasattr(last_msg, "content") else ""
    # Handle multi-part content (list of content blocks)
    if isinstance(answer_text, list):
        answer_text = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in answer_text
        )

    # De-duplicate sources by ID, preserving order.
    # Only keep Presentation, Session, Speaker — these are navigable citations.
    _CITABLE_LABELS = {"Presentation", "Session", "Speaker"}
    seen: set[str] = set()
    unique_sources: list[dict[str, Any]] = []
    for s in state.get("collected_sources") or []:
        if s["id"] not in seen and s.get("label") in _CITABLE_LABELS:
            seen.add(s["id"])
            unique_sources.append(s)

    # Build citation map
    sources_output = []
    for i, src in enumerate(unique_sources):
        sources_output.append({
            "id": src["id"],
            "name": src["name"],
            "label": src["label"],
            "citation": i + 1,
            "score": round(src.get("score", 0), 4),
        })

    # Clean leaked IDs from answer
    answer_text = re.sub(r"\s*\((?:id=\S+(?:,\s*)?)+\)", "", answer_text)
    answer_text = re.sub(r"\bid=\S+", "", answer_text)

    # Strip trailing "References" / "Sources" section the LLM sometimes adds
    answer_text = re.sub(
        r"\n+(?:#{1,4}\s*)?(?:\*\*)?(?:References|Sources|Bibliography)(?:\*\*)?:?\s*\n.*",
        "",
        answer_text,
        flags=re.DOTALL | re.IGNORECASE,
    ).rstrip()

    all_node_ids = list(state.get("visited_node_ids") or set())
    all_link_ids = list(state.get("visited_link_ids") or set())

    return {
        "answer": answer_text,
        "subgraph": {"node_ids": all_node_ids, "link_ids": all_link_ids},
        "sources": sources_output,
    }


def _should_continue(state: AgentState) -> str:
    """Route: tool_calls present → tool_node, otherwise → finalize."""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tool_node"
    return "finalize"


def build_agent_graph() -> Any:
    """Construct and compile the LangGraph agent."""
    builder = StateGraph(AgentState)

    builder.add_node("llm_call", llm_call)
    builder.add_node("tool_node", tool_node)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "llm_call")
    builder.add_conditional_edges("llm_call", _should_continue, ["tool_node", "finalize"])
    builder.add_edge("tool_node", "llm_call")
    builder.add_edge("finalize", END)

    return builder.compile()
