from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from neo4j import AsyncDriver
from openai import AsyncOpenAI
from sse_starlette.sse import EventSourceResponse

from app.dependencies import get_neo4j_driver, get_openai_client
from app.models.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    SubgraphHighlight,
    UserInfo,
)
from app.routers.auth import get_current_user
from app.services.agent_graph import build_agent_graph
from app.services.chat import add_message, compact_if_needed, get_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Build the agent graph once at module level
_agent = build_agent_graph()


def _build_agent_input(question: str, history: list[ChatMessage]) -> dict:
    """Build the initial state for the agent graph."""
    return {
        "messages": [HumanMessage(content=question)],
        "question": question,
        "chat_history": [
            {"role": msg.role, "content": msg.content} for msg in history
        ],
        # Initialize reducer-managed fields so LangGraph has base values to merge
        "visited_node_ids": set(),
        "visited_link_ids": set(),
        "collected_sources": [],
    }


def _build_config(driver: AsyncDriver, openai_client: AsyncOpenAI) -> dict:
    """Build RunnableConfig with neo4j_driver and openai_client."""
    return {
        "configurable": {
            "neo4j_driver": driver,
            "openai_client": openai_client,
        }
    }


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: UserInfo = Depends(get_current_user),
    driver: AsyncDriver = Depends(get_neo4j_driver),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
) -> ChatResponse:
    """Run agent pipeline and return answer with subgraph highlight."""
    user_id = user.email
    add_message(user_id, "user", body.message)
    await compact_if_needed(user_id, openai_client)
    history = get_history(user_id)

    try:
        result = await _agent.ainvoke(
            _build_agent_input(body.message, history),
            config=_build_config(driver, openai_client),
        )
    except Exception:
        logger.exception("Agent pipeline failed")
        raise HTTPException(status_code=500, detail="Failed to process query")

    answer = result.get("answer", "I could not find a relevant answer.")
    subgraph = result.get("subgraph", {})
    sources = result.get("sources", [])

    add_message(user_id, "assistant", answer)

    return ChatResponse(
        answer=answer,
        subgraph=SubgraphHighlight(
            node_ids=subgraph.get("node_ids", []),
            link_ids=subgraph.get("link_ids", []),
        ),
        sources=sources,
    )


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    user: UserInfo = Depends(get_current_user),
    driver: AsyncDriver = Depends(get_neo4j_driver),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
):
    """SSE streaming endpoint with agent reasoning trace."""
    user_id = user.email
    add_message(user_id, "user", body.message)
    await compact_if_needed(user_id, openai_client)
    history = get_history(user_id)

    async def event_generator():
        try:
            agent_input = _build_agent_input(body.message, history)
            config = _build_config(driver, openai_client)

            final_answer = ""
            final_subgraph: dict = {}
            final_sources: list = []

            async for event, chunk in _agent.astream(
                agent_input,
                config=config,
                stream_mode=["updates", "custom"],
            ):
                if event == "custom":
                    # Custom events from get_stream_writer() in tools/nodes
                    event_type = chunk.get("type", "thinking")
                    yield {
                        "event": event_type,
                        "data": json.dumps(chunk),
                    }

                elif event == "updates":
                    # State updates from graph nodes
                    if "finalize" in chunk:
                        finalize_data = chunk["finalize"]
                        final_answer = finalize_data.get("answer", "")
                        final_subgraph = finalize_data.get("subgraph", {})
                        final_sources = finalize_data.get("sources", [])

                        # Stream the answer in chunks for typing effect
                        chunk_size = 80
                        for i in range(0, len(final_answer), chunk_size):
                            text_chunk = final_answer[i : i + chunk_size]
                            yield {
                                "event": "token",
                                "data": json.dumps({"content": text_chunk}),
                            }

            add_message(user_id, "assistant", final_answer)

            yield {
                "event": "done",
                "data": json.dumps({
                    "answer": final_answer,
                    "subgraph": final_subgraph,
                    "sources": final_sources,
                }),
            }
        except Exception:
            logger.exception("SSE agent pipeline failed")
            yield {
                "event": "error",
                "data": json.dumps({"detail": "Failed to process query"}),
            }

    return EventSourceResponse(event_generator())


@router.get("/history", response_model=list[ChatMessage])
async def chat_history(
    user: UserInfo = Depends(get_current_user),
) -> list[ChatMessage]:
    """Return the chat history for the current user session."""
    user_id = user.email
    return get_history(user_id)
