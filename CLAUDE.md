# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Interactive SPA for exploring a knowledge graph built from the AI in AEC 2026 conference transcripts (Helsinki). Users view a 3D force-directed graph, ask natural language questions via GraphRAG, and see relevant subgraphs highlighted in real time.

## Architecture

Monorepo with three main components:

- **`frontend/`** — React 19 + TypeScript + Vite SPA. 3D graph via `react-force-graph-3d` (ThreeJS/WebGL). Zustand for state. Tailwind CSS v4 + Framer Motion for styling/animation.
- **`backend/`** — Python FastAPI async API. Serves the graph data, handles chat via GraphRAG pipeline, manages user sessions. All LLM and embedding calls go through OpenRouter (`openai/gpt-4.1` for chat, `google/gemini-2.5-flash` for extraction, `openai/text-embedding-3-large` for embeddings).
- **`backend/pipeline/`** — Offline graph construction pipeline. Parses transcripts → LLM entity/relationship extraction → entity resolution → NLP enrichment (spaCy) → embedding generation → Neo4j load.

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
| LLM | GPT-5.4 via OpenRouter (OpenAI-compatible API) |
| Embeddings | OpenAI `text-embedding-3-large` (3072 dims) |
| NLP | spaCy `en_core_web_trf`, rapidfuzz, keybert |
| Auth | JWT (PyJWT), user records in SQLite |
| GraphRAG | `neo4j-graphrag-python` (VectorCypherRetriever) |

## Commands

### Development
```bash
# Start all services (Neo4j + backend + frontend)
docker compose up

# Backend only (with hot reload)
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend only (with HMR)
cd frontend && npm run dev

# Neo4j only
docker compose up neo4j
```

### Graph Pipeline
```bash
# Run full extraction pipeline (parse → extract → resolve → enrich → embed → load)
cd backend && python -m pipeline.run_pipeline

# Run individual stages
cd backend && python -m pipeline.run_pipeline --stage parse
cd backend && python -m pipeline.run_pipeline --stage extract
cd backend && python -m pipeline.run_pipeline --stage resolve
cd backend && python -m pipeline.run_pipeline --stage embed
cd backend && python -m pipeline.run_pipeline --stage load
```

### Testing
```bash
# Backend tests
cd backend && pytest
cd backend && pytest tests/test_graphrag.py -k "test_retrieval"

# Frontend tests
cd frontend && npm test
cd frontend && npm test -- --run src/hooks/useChat.test.ts

# Linting
cd backend && ruff check . && ruff format --check .
cd frontend && npm run lint
```

### Package Management
```bash
# Backend (uv)
cd backend && uv add <package>
cd backend && uv sync

# Frontend (npm)
cd frontend && npm install <package>
```

## Neo4j Schema

**Node labels:** Session, Speaker, Organization, Topic, Technology, Concept, Project
**Key relationships:** SPOKE_AT, AFFILIATED_WITH, COVERS_TOPIC, DISCUSSED, PRESENTED, RELATES_TO, USED_BY, MENTIONS_TECHNOLOGY, MENTIONS_PROJECT, USES_TECHNOLOGY, LED_BY, SUBTOPIC_OF

All nodes have `id` (unique string), `name`, and `embedding` (3072-dim float vector) properties. Vector indexes exist on each node label for cosine similarity search.

## GraphRAG Query Pipeline (6 steps)

1. **Embed query** — OpenAI `text-embedding-3-large`
2. **Semantic search** — VectorCypherRetriever across all node type indexes, top 20 candidates
3. **LLM relevance filter** — GPT-5.4 selects ~5-10 seed nodes from candidates
4. **Graph expansion** — APOC `subgraphAll` 2 hops from seed nodes
5. **LLM subgraph filter** — GPT-5.4 filters expanded subgraph and generates answer
6. **Return** — Answer text + `node_ids`/`link_ids` for frontend highlighting

## Frontend UX Flow

1. **Initial:** Full-screen 3D graph, auto-rotating, dark background (#000011). Text input floating at bottom center.
2. **First question:** Signup modal (name/email/company) → JWT issued → question sent to `/api/chat`
3. **After signup:** Chat sidebar slides in from right. Text input moves to sidebar. Graph shrinks to fill remaining space.
4. **On answer:** Relevant subgraph nodes highlighted (opacity 1.0), all others dimmed (opacity ~0.08). Camera flies to highlighted cluster.

## API Endpoints

```
GET  /api/health          — Status + Neo4j connectivity
GET  /api/graph           — Full graph (nodes + links, no embeddings)
POST /api/register        — {name, email, company} → {session_id, token}
GET  /api/session         — Validate JWT, return user info
POST /api/chat            — {message} → SSE stream: {answer, subgraph{node_ids, link_ids}, sources}
GET  /api/chat/history    — Session message history
```

## Environment Variables

```
OPENROUTER_API_KEY=sk-or-...
OPENAI_API_KEY=sk-...
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=dev_password
JWT_SECRET=<random-secret>
APP_URL=http://localhost:5173
```

## Key Conventions

- OpenRouter is accessed via the OpenAI SDK with `base_url="https://openrouter.ai/api/v1"` — never use a custom HTTP client
- All Neo4j writes use `MERGE` (not `CREATE`) so the pipeline is idempotent
- Chat memory is session-scoped (in-memory dict keyed by JWT subject, with TTL). Compaction triggers when history exceeds ~8000 tokens
- Node colors by type: Session=amber, Speaker=indigo, Organization=emerald, Topic=rose, Technology=blue, Concept=purple, Project=cyan
- The graph is small (~200 nodes, ~400 edges) — always send the full graph to the frontend in one request, no pagination
