from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import get_settings
from app.models.schemas import ChatMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory chat session store (keyed by user_id / email)
# ---------------------------------------------------------------------------

chat_sessions: dict[str, list[ChatMessage]] = {}

_CHAR_LIMIT = 32_000  # ~8 000 tokens at ~4 chars/token


def add_message(user_id: str, role: str, content: str) -> None:
    """Append a message to a user's chat history."""
    if user_id not in chat_sessions:
        chat_sessions[user_id] = []
    chat_sessions[user_id].append(ChatMessage(role=role, content=content))


def get_history(user_id: str) -> list[ChatMessage]:
    """Return the full chat history for a user."""
    return list(chat_sessions.get(user_id, []))


async def compact_if_needed(user_id: str, openai_client: AsyncOpenAI) -> None:
    """If total chars exceed the limit, summarise older messages."""
    messages = chat_sessions.get(user_id)
    if not messages:
        return

    total_chars = sum(len(m.content) for m in messages)
    if total_chars <= _CHAR_LIMIT:
        return

    # Keep the most recent 4 messages intact; summarise the rest
    keep_recent = 4
    if len(messages) <= keep_recent:
        return

    older = messages[:-keep_recent]
    recent = messages[-keep_recent:]

    conversation_text = "\n".join(
        f"{m.role}: {m.content}" for m in older
    )

    try:
        settings = get_settings()
        response = await openai_client.chat.completions.create(
            model=settings.resolve_model("openai/gpt-4.1"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarise the following conversation concisely, "
                        "preserving key facts, questions, and answers. "
                        "Output only the summary."
                    ),
                },
                {"role": "user", "content": conversation_text},
            ],
            max_tokens=512,
        )
        summary = response.choices[0].message.content or ""
    except Exception:
        logger.exception("Failed to compact chat history")
        return

    # Replace history with a summary message + the recent messages
    chat_sessions[user_id] = [
        ChatMessage(role="system", content=f"[Conversation summary] {summary}"),
        *recent,
    ]
