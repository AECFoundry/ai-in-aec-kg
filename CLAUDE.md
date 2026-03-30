# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Interactive SPA for exploring a knowledge graph built from the AI in AEC 2026 conference transcripts (Helsinki). Users view a 3D force-directed graph, ask natural language questions via agentic GraphRAG, and see relevant subgraphs highlighted in real time.

## Architecture

Monorepo with three main components:

- **`frontend/`** — React 19 + TypeScript + Vite SPA. 3D graph via `react-force-graph-3d` (ThreeJS/WebGL). Zustand for state. Tailwind CSS v4 + Framer Motion for styling/animation.
- **`backend/`** — Python FastAPI async API. Serves the graph data, handles chat via agentic GraphRAG pipeline (LangGraph). All LLM and embedding calls go through OpenRouter.
- **`backend/pipeline/`** — Offline graph construction pipeline. Parses transcripts → LLM entity/relationship extraction → entity resolution → presentation decomposition → NLP enrichment (spaCy) → embedding generation → Neo4j load.

**Data flow:** Transcripts → Pipeline → Neo4j ← Backend API ← Frontend SPA

## Data Source

`AI_in_AEC_2026_Snapsight_Summaries.txt` — 12,342 lines, 15 sessions. Structure per session:
```
================================================================================
SESSION N: <title>
================================================================================
--- LIVE TEXT ---
<transcription paragraphs>
--- SUMMARY ---
Summary
<summary paragraphs>
Speakers
<initials>
<name>
<title or "-">
<organization>
(repeating per speaker)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind v4, Framer Motion, Zustand |
| 3D Graph | `react-force-graph-3d` + `three-spritetext` |
| Backend | FastAPI, Python 3.12+, uv package manager |
| Graph DB | Neo4j 5.x Community (Docker) with APOC plugin |
| LLM | GPT-4.1 via OpenRouter for agent reasoning |
| Extraction | Gemini 2.5 Flash via OpenRouter for entity extraction |
| Embeddings | `text-embedding-3-large` (3072 dims) via OpenRouter |
| NLP | spaCy `en_core_web_sm`, rapidfuzz, KeyBERT |
| Agent | LangGraph StateGraph + langchain-openai (agentic ReAct loop) |

## Commands

### Development
```bash
# Neo4j (required first)
docker compose up -d neo4j

# Backend (with hot reload)
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Frontend (with HMR)
cd frontend && npm run dev
```

### Seed Data (quick start — no API keys needed)
```bash
# Load pre-built graph data into Neo4j (ships with repo)
cd backend && uv run python -m pipeline.seed
```

### Graph Pipeline (rebuild from scratch — requires LLM API key)
```bash
# Run full pipeline (parse → extract → resolve → presentations → enrich → embed → load)
cd backend && uv run python -m pipeline.run_pipeline

# Run individual stages
cd backend && uv run python -m pipeline.run_pipeline --stage parse
cd backend && uv run python -m pipeline.run_pipeline --stage extract
cd backend && uv run python -m pipeline.run_pipeline --stage resolve
cd backend && uv run python -m pipeline.run_pipeline --stage presentations
cd backend && uv run python -m pipeline.run_pipeline --stage enrich
cd backend && uv run python -m pipeline.run_pipeline --stage embed
cd backend && uv run python -m pipeline.run_pipeline --stage load

# Generate detailed presentation summaries (post-pipeline, writes to Neo4j)
cd backend && uv run python -m pipeline.generate_detailed_summaries
```

### Testing
```bash
cd backend && uv run pytest
cd frontend && npm test
```

### Linting
```bash
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && npm run lint
```

## Neo4j Schema

**Node labels:** Session, Presentation, TranscriptChunk, Speaker, Organization, Topic, Technology, Concept, Project
**Key relationships:** SPOKE_AT, AFFILIATED_WITH, COVERS_TOPIC, DISCUSSED, PRESENTED, RELATES_TO, USED_BY, MENTIONS_TECHNOLOGY, MENTIONS_PROJECT, USES_TECHNOLOGY, LED_BY, SUBTOPIC_OF, PART_OF, PRESENTED_BY, MENTIONS, CHUNK_OF

All nodes have `id` (unique string), `name`, and `embedding` (3072-dim float vector) properties. Vector indexes exist on each node label for cosine similarity search. TranscriptChunk nodes contain ~400-word excerpts from formatted presentation transcripts and link to Presentation via CHUNK_OF. Presentation nodes have `transcript` (full formatted text) and `detailed_summary` (LLM-generated 400-600 word summary).

## Agentic GraphRAG (LangGraph)

LangGraph StateGraph with ReAct loop: `llm_call → [tool_calls?] → tool_node → llm_call → ... → finalize → END`

**Tools:** `vector_search_nodes`, `get_node_neighbors`, `find_paths`, `expand_subgraph`, `get_node_details`, `run_cypher_query`

The agent autonomously decides which tools to call based on query intent. SSE streams reasoning trace (thinking, tool_call, tool_progress, tool_result) + answer tokens to the frontend.

## Frontend UX Flow

1. **Initial:** Full-screen 3D graph with left sidebar for node browsing. Auto-rotating, dark background (#000011). Text input floating at bottom center.
2. **First question:** Chat sidebar slides in from right. Text input moves to sidebar. Graph shrinks to fill remaining space.
3. **On answer:** Agent reasoning trace streams in real time. Relevant subgraph nodes highlighted (opacity 1.0), all others dimmed. Camera flies to highlighted cluster. Numbered citation badges link back to source nodes.

## API Endpoints

```
GET  /api/health          — Status + Neo4j connectivity
GET  /api/graph           — Full graph (nodes + links, no embeddings)
POST /api/chat            — {message} → JSON: {answer, subgraph, sources}
POST /api/chat/stream     — {message} → SSE: thinking, tool_*, token, done events
GET  /api/chat/history    — Session message history
GET  /api/voice/capabilities — {tts_available: bool}
POST /api/voice/tts       — {text} → audio/mpeg stream (requires OPENAI_API_KEY)
```

## Environment Variables

All configuration via a single `.env` file at the repo root (see `.env.example`):

```
OPENROUTER_API_KEY=sk-or-...   # Option A: OpenRouter (recommended, supports Gemini)
OPENAI_API_KEY=sk-...          # Option B: Direct OpenAI API
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=dev_password_kg2026
APP_URL=http://localhost:5173
```

Set one of `OPENROUTER_API_KEY` or `OPENAI_API_KEY`. If both are set, OpenRouter takes precedence. When using direct OpenAI, `google/gemini-*` models fall back to `gpt-4.1-mini`.

## Key Conventions

- OpenRouter is accessed via the OpenAI SDK with `base_url="https://openrouter.ai/api/v1"` — never use a custom HTTP client
- All Neo4j writes use `MERGE` (not `CREATE`) so the pipeline is idempotent
- The loader cleans up stale Presentation nodes before loading new ones to prevent duplicates across re-runs
- Chat memory is in-memory with automatic compaction when history exceeds ~8000 tokens
- Node colors by type: Session=amber, Presentation=yellow, Speaker=indigo, Organization=emerald, Topic=rose, Technology=blue, Concept=purple, Project=cyan
- The graph has ~1,700 nodes and ~2,500 edges (TranscriptChunks excluded from 3D view). Full graph sent to frontend in one request
