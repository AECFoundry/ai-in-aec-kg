from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
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
from app.services.chat import add_message, compact_if_needed, get_history
from app.services.graphrag import query_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: UserInfo = Depends(get_current_user),
    driver: AsyncDriver = Depends(get_neo4j_driver),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
) -> ChatResponse:
    """Run GraphRAG pipeline and return answer with subgraph highlight."""
    user_id = user.email  # use email as session key

    # Record user message
    add_message(user_id, "user", body.message)

    # Compact memory if needed
    await compact_if_needed(user_id, openai_client)

    # Get conversation context for the LLM
    history = get_history(user_id)

    try:
        result = await query_graph(
            question=body.message,
            neo4j_driver=driver,
            openai_client=openai_client,
            chat_history=history,
        )
    except Exception:
        logger.exception("GraphRAG pipeline failed")
        raise HTTPException(status_code=500, detail="Failed to process query")

    answer = result.get("answer", "I could not find a relevant answer.")
    subgraph = result.get("subgraph", {})
    sources = result.get("sources", [])

    # Record assistant response
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
    """SSE streaming endpoint for chat responses."""
    user_id = user.email
    add_message(user_id, "user", body.message)
    await compact_if_needed(user_id, openai_client)
    history = get_history(user_id)

    async def event_generator():
        try:
            result = await query_graph(
                question=body.message,
                neo4j_driver=driver,
                openai_client=openai_client,
                chat_history=history,
            )
            answer = result.get("answer", "I could not find a relevant answer.")
            subgraph = result.get("subgraph", {})
            sources = result.get("sources", [])

            add_message(user_id, "assistant", answer)

            # Stream the answer in chunks
            chunk_size = 80
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i : i + chunk_size]
                yield {
                    "event": "token",
                    "data": json.dumps({"content": chunk}),
                }

            # Send final event with subgraph and sources
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "answer": answer,
                        "subgraph": subgraph,
                        "sources": sources,
                    }
                ),
            }
        except Exception:
            logger.exception("SSE GraphRAG pipeline failed")
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
