"""Extract individual presentations from session summaries and transcripts using LLM."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class Presentation:
    id: str
    session_id: str
    title: str
    summary: str
    transcript: str  # formatted transcript extracted from live_text
    speakers: list[str]  # speaker names
    order: int  # position within session (1-based)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Presentation:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    text = re.sub(r"-+", "_", text)
    return text.strip("_")


# -- Phase 1: Extract presentation metadata from summary --

_METADATA_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "presentation_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": (
                        "Think step-by-step: identify each distinct presentation or "
                        "talk within the session. Consider speaker changes, topic shifts, "
                        "and paragraph structure in the summary."
                    ),
                },
                "presentations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": (
                                    "A concise, descriptive title for this presentation "
                                    "(not the session title). E.g. 'AI-Driven Structural "
                                    "Analysis with Robot' or 'CEO Playbook for AI Transformation'."
                                ),
                            },
                            "summary": {
                                "type": "string",
                                "description": (
                                    "A 2-4 sentence summary of what was presented, "
                                    "including key points and technologies mentioned."
                                ),
                            },
                            "speakers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Full names of the speaker(s) who gave this presentation. "
                                    "Use the exact names from the speaker list provided."
                                ),
                            },
                        },
                        "required": ["title", "summary", "speakers"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["reasoning", "presentations"],
            "additionalProperties": False,
        },
    },
}


def _extract_metadata_for_session(
    client: OpenAI,
    session: dict,
    *,
    model: str = "",
) -> list[dict]:
    """Use LLM to identify individual presentations from session summary."""
    if not model:
        from pipeline.llm_utils import resolve_model
        model = resolve_model("openai/gpt-4.1")

    summary = session.get("summary_text", "")
    if not summary or len(summary.strip()) < 50:
        return []

    speakers = session.get("speakers", [])
    speaker_list = "\n".join(
        f"- {s['name']} ({s.get('organization', 'unknown')})"
        for s in speakers
    ) or "No speaker list available"

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert at analyzing conference session transcripts. "
                "Given a session summary and speaker list, identify each individual "
                "presentation or talk within the session.\n\n"
                "Guidelines:\n"
                "- A keynote with one speaker is a single presentation.\n"
                "- A multi-speaker session typically has one presentation per speaker "
                "or speaker group.\n"
                "- Panel discussions are a single presentation with multiple speakers.\n"
                "- Opening/closing remarks by a chair are NOT separate presentations "
                "unless substantive.\n"
                "- Each presentation should have a specific, descriptive title "
                "(NOT the session title).\n"
                "- Attribute speakers accurately using the provided speaker list."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Session: {session['title']}\n\n"
                f"Speakers:\n{speaker_list}\n\n"
                f"Summary:\n{summary}"
            ),
        },
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.1,
            response_format=_METADATA_SCHEMA,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        return parsed.get("presentations", [])
    except Exception:
        logger.exception(
            "Failed to extract presentations for session %s",
            session.get("session_number"),
        )
        return []


# -- Phase 2: Extract and format per-presentation transcripts from live_text --

_TRANSCRIPT_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "transcript_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "presentations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "The presentation title (must match one from the list).",
                            },
                            "transcript": {
                                "type": "string",
                                "description": (
                                    "The formatted transcript for this presentation. "
                                    "Clean, readable prose with proper paragraphs. "
                                    "Preserve all substantive content and speaker attributions. "
                                    "Remove filler words, false starts, and transcription artifacts."
                                ),
                            },
                        },
                        "required": ["title", "transcript"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["presentations"],
            "additionalProperties": False,
        },
    },
}


def _extract_transcripts_for_session(
    client: OpenAI,
    session: dict,
    presentation_titles: list[str],
    *,
    model: str = "",
) -> dict[str, str]:
    """Extract and format per-presentation transcripts from session live_text.

    Returns a dict mapping presentation title -> formatted transcript.
    """
    if not model:
        from pipeline.llm_utils import resolve_model
        model = resolve_model("openai/gpt-4.1")
    live_text = session.get("live_text", "")
    if not live_text or len(live_text.strip()) < 100:
        return {}

    titles_str = "\n".join(f"- {t}" for t in presentation_titles)

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert editor who transforms raw speech-to-text conference "
                "transcripts into clean, readable documents.\n\n"
                "You will receive a raw transcript from a conference session and a list of "
                "individual presentations that occurred within the session. Your task:\n\n"
                "1. Identify which portions of the transcript correspond to each presentation.\n"
                "2. For each presentation, produce a clean, formatted transcript that:\n"
                "   - Removes filler words (um, uh, you know, like, so basically)\n"
                "   - Fixes obvious transcription errors and garbled text\n"
                "   - Adds proper paragraph breaks at topic transitions\n"
                "   - Preserves ALL substantive content, technical details, and examples\n"
                "   - Attributes quotes and statements to speakers where clear\n"
                "   - Maintains the speaker's voice and intent\n"
                "   - Omits moderator housekeeping (introductions, time reminders) unless substantive\n"
                "3. If the transcript is too garbled to extract meaningful content for a presentation, "
                "provide a brief note explaining this.\n"
                "4. Do NOT invent content. Only include what is in the transcript."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Session: {session['title']}\n\n"
                f"Presentations to extract:\n{titles_str}\n\n"
                f"--- RAW TRANSCRIPT ---\n{live_text}"
            ),
        },
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=16000,
            temperature=0.1,
            response_format=_TRANSCRIPT_SCHEMA,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)

        result: dict[str, str] = {}
        for item in parsed.get("presentations", []):
            title = item.get("title", "").strip()
            transcript = item.get("transcript", "").strip()
            if title and transcript:
                result[title] = transcript
        return result
    except Exception:
        logger.exception(
            "Failed to extract transcripts for session %s",
            session.get("session_number"),
        )
        return {}


# -- Main orchestration --


def extract_presentations(
    sessions_data: list[dict],
    client: OpenAI,
) -> list[Presentation]:
    """Extract presentations with formatted transcripts from all sessions."""
    all_presentations: list[Presentation] = []

    for session in sessions_data:
        session_num = session["session_number"]
        session_id = f"session_{session_num}"

        logger.info(
            "Extracting presentations from session %d: %s",
            session_num,
            session["title"],
        )

        # Phase 1: Extract metadata (titles, summaries, speakers)
        raw_presentations = _extract_metadata_for_session(client, session)
        if not raw_presentations:
            logger.info("  No presentations found in session %d", session_num)
            continue

        titles = [p.get("title", "") for p in raw_presentations if p.get("title")]

        # Phase 2: Extract and format transcripts from live_text
        logger.info(
            "  Formatting transcripts for %d presentations in session %d",
            len(titles),
            session_num,
        )
        transcripts = _extract_transcripts_for_session(
            client, session, titles
        )

        # Match transcripts to presentations (fuzzy title match)
        for i, pres in enumerate(raw_presentations, start=1):
            title = pres.get("title", "").strip()
            if not title:
                continue

            # Try exact match first, then case-insensitive
            transcript = transcripts.get(title, "")
            if not transcript:
                title_lower = title.lower()
                for t_title, t_text in transcripts.items():
                    if t_title.lower() == title_lower:
                        transcript = t_text
                        break

            # Fallback: partial match
            if not transcript:
                title_lower = title.lower()
                for t_title, t_text in transcripts.items():
                    if title_lower in t_title.lower() or t_title.lower() in title_lower:
                        transcript = t_text
                        break

            pres_id = f"presentation_s{session_num}_{_slugify(title)[:60]}"

            all_presentations.append(
                Presentation(
                    id=pres_id,
                    session_id=session_id,
                    title=title,
                    summary=pres.get("summary", ""),
                    transcript=transcript,
                    speakers=pres.get("speakers", []),
                    order=i,
                )
            )

        logger.info(
            "  Found %d presentations in session %d (%d with transcripts)",
            len(raw_presentations),
            session_num,
            sum(1 for p in all_presentations if p.session_id == session_id and p.transcript),
        )

    logger.info("Total presentations extracted: %d", len(all_presentations))
    return all_presentations
