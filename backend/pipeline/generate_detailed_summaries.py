"""Generate detailed summaries for all presentations using their full transcripts."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from neo4j import AsyncGraphDatabase
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Load env from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from pipeline.llm_utils import get_api_key, get_base_url, resolve_model  # noqa: E402

SYSTEM_PROMPT = """\
You are an expert technical writer summarizing conference presentations for a knowledge graph explorer.

Given a full formatted transcript of a conference presentation, produce a detailed summary (400-600 words) that:
- Opens with the speaker's main thesis or argument
- Covers all key points, technologies, frameworks, and methodologies discussed
- Includes specific examples, case studies, or demos mentioned
- Notes any conclusions, recommendations, or future directions
- Preserves technical specificity — name tools, standards, companies, and metrics
- Uses clear prose paragraphs (no bullet points or headers)
- Maintains the speaker's perspective and voice

Write the summary in third person (e.g. "The speaker demonstrated..." or use their name)."""


def generate_summary(client: OpenAI, title: str, transcript: str, model: str = "") -> str:
    """Generate a detailed summary from a presentation transcript."""
    if not model:
        model = resolve_model("openai/gpt-4.1")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Presentation: {title}\n\n--- TRANSCRIPT ---\n{transcript}"},
        ],
        max_tokens=1500,
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip()


async def main() -> None:
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    client = OpenAI(base_url=get_base_url(), api_key=get_api_key())
    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    # Fetch all presentations with transcripts that don't yet have detailed summaries
    async with driver.session() as session:
        result = await session.run("""
            MATCH (p:Presentation)
            WHERE p.transcript IS NOT NULL AND p.detailed_summary IS NULL
            RETURN p.id AS id, p.title AS title, p.transcript AS transcript
            ORDER BY p.id
        """)
        presentations = await result.data()

    logger.info("Found %d presentations needing detailed summaries", len(presentations))

    for i, pres in enumerate(presentations, 1):
        pres_id = pres["id"]
        title = pres["title"]
        transcript = pres["transcript"]

        if not transcript or len(transcript.strip()) < 200:
            logger.warning("  [%d/%d] Skipping %s — transcript too short", i, len(presentations), pres_id)
            continue

        logger.info("  [%d/%d] Generating summary for: %s", i, len(presentations), title)

        try:
            summary = generate_summary(client, title, transcript)
        except Exception:
            logger.exception("  Failed to generate summary for %s", pres_id)
            continue

        if not summary:
            logger.warning("  Empty summary for %s", pres_id)
            continue

        # Write back to Neo4j
        async with driver.session() as session:
            await session.run(
                "MATCH (p:Presentation {id: $id}) SET p.detailed_summary = $summary",
                id=pres_id,
                summary=summary,
            )

        logger.info("  Saved %d chars for %s", len(summary), title)

    await driver.close()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
