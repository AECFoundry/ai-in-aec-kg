"""LangGraph agent state definition."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


def _merge_sets(left: set[str], right: set[str]) -> set[str]:
    return left | right


def _merge_lists(left: list[dict], right: list[dict]) -> list[dict]:
    return left + right


class AgentState(TypedDict):
    """State flowing through the LangGraph agent."""

    # Core message history (managed by add_messages reducer)
    messages: Annotated[list[AnyMessage], add_messages]

    # Original user question (set once at entry)
    question: str

    # Prior conversation turns for context
    chat_history: list[dict[str, str]]

    # Accumulated node/link IDs across all tool calls (set-union reducers)
    visited_node_ids: Annotated[set[str], _merge_sets]
    visited_link_ids: Annotated[set[str], _merge_sets]

    # Sources from vector searches for citation building (list-concat reducer)
    collected_sources: Annotated[list[dict[str, Any]], _merge_lists]

    # Final output fields (set by the finalize node)
    answer: str
    subgraph: dict[str, list[str]]
    sources: list[dict[str, Any]]
