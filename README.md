# AI in AEC Knowledge Graph Explorer

An interactive 3D knowledge graph explorer that transforms raw conference transcripts into a navigable web of speakers, organizations, topics, technologies, concepts, and presentations — powered by agentic GraphRAG.

Built from the [AI in AEC 2026](https://www.ainaec.com/) conference transcripts (Helsinki, March 2026): 15 sessions, 50+ speakers, ~1,700 nodes, ~2,500 relationships.

https://github.com/user-attachments/assets/DEMO_VIDEO_PLACEHOLDER

## What It Does

- **3D force-directed graph** — explore the full conference knowledge graph in real time with color-coded node types, auto-rotation, and camera animation
- **Natural language questions** — ask things like *"Which speakers discussed digital twins in facility management?"* or *"How is BIM connected to sustainability?"*
- **Agentic GraphRAG** — an AI agent autonomously decides how to search the graph (vector search, graph traversal, path finding, Cypher queries) and streams its reasoning in real time
- **Cited answers** — every response includes numbered citations linking back to specific presentations and speakers, with click-to-fly navigation
- **Voice interaction** — tap the voice orb to ask questions by voice (Web Speech STT), hear answers spoken back via OpenAI TTS with sentence-level streaming for near-instant audio playback
- **Node browser** — left sidebar for browsing all nodes by type, with search and click-to-focus

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────┐
│   React 19 SPA  │────▶│  FastAPI API  │────▶│  Neo4j  │
│  3D Force Graph │◀────│  LangGraph   │◀────│  + APOC │
│  Zustand + SSE  │     │  Agent       │     │  Vector │
└─────────────────┘     └──────────────┘     └─────────┘
                              │
                    ┌─────────┴─────────┐
                    │    OpenRouter      │
                    │  GPT-4.1 (agent)   │
                    │  Gemini 2.5 Flash  │
                    │  text-embed-3-lg   │
                    └───────────────────┘
```

**Three layers:**

1. **Frontend** — React 19 + TypeScript + Vite. 3D graph via `react-force-graph-3d` (Three.js/WebGL). Tailwind CSS v4, Framer Motion, Zustand state management.
2. **Backend** — FastAPI (async Python). LangGraph agent with 6 tools for graph exploration. SSE streaming for real-time reasoning trace + answer tokens.
3. **Pipeline** — 7-stage offline pipeline: parse → LLM extraction → entity resolution → presentation decomposition → NLP enrichment → embedding → Neo4j load.

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (for Neo4j)
- [Node.js](https://nodejs.org/) 20+
- [Python](https://www.python.org/) 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- An LLM API key — **either** [OpenRouter](https://openrouter.ai/keys) or [OpenAI](https://platform.openai.com/api-keys) (needed for the chat agent; **not** needed to load the graph)

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/ai-in-aec-kg.git
cd ai-in-aec-kg

cp .env.example .env
# Edit .env — at minimum set NEO4J_PASSWORD (default: dev_password_kg2026)
# Add an API key to use the chat agent (see below)
```

**LLM provider options** — set one in your `.env`:

| Provider | Env var | Notes |
|----------|---------|-------|
| **OpenRouter** | `OPENROUTER_API_KEY` | Recommended. Supports all models including Gemini for extraction. |
| **OpenAI** | `OPENAI_API_KEY` | Uses GPT-4.1-mini as fallback for extraction (Gemini unavailable). |

If both keys are set, OpenRouter takes precedence. An API key is required for the **chat agent** but not for loading and browsing the graph.

### 2. Start Neo4j

```bash
docker compose up -d neo4j
# Wait for healthy status:
docker compose ps
```

### 3. Install dependencies

```bash
# Backend
cd backend
uv sync
uv run python -m spacy download en_core_web_sm
cd ..

# Frontend
cd frontend
npm install
cd ..
```

### 4. Load the graph

**Option A — Seed data (recommended, no API keys needed):**

Pre-built graph data ships with the repo. Just load it into Neo4j:

```bash
cd backend
uv run python -m pipeline.seed
```

This loads ~1,700 nodes, ~2,500 relationships, vector embeddings, and detailed presentation summaries — everything you need to explore the app.

**Option B — Rebuild from scratch (requires LLM API key):**

Run the full extraction pipeline to rebuild the graph from conference transcripts:

```bash
cd backend
uv run python -m pipeline.run_pipeline
uv run python -m pipeline.generate_detailed_summaries
```

The pipeline runs 7 stages in order:

| Stage | What it does | API calls |
|-------|-------------|-----------|
| **parse** | Splits transcript file into 15 session objects | None |
| **extract** | LLM extracts entities and relationships from each session | ~15 calls (Gemini 2.5 Flash) |
| **resolve** | Deduplicates entities via fuzzy matching (rapidfuzz) | None |
| **presentations** | LLM identifies individual presentations within sessions + formats transcripts | ~30 calls (GPT-5.4) |
| **enrich** | spaCy NER + KeyBERT keyword extraction | None (local NLP) |
| **embed** | Generates 3072-dim vector embeddings for all nodes | ~20 batch calls (text-embedding-3-large) |
| **load** | Writes everything to Neo4j with MERGE (idempotent) | None |

Each stage caches its output to `backend/data/pipeline_cache/`, so you can re-run individual stages without repeating earlier ones:

```bash
uv run python -m pipeline.run_pipeline --stage load  # re-load only
```

### 5. Start the app

In two terminals:

```bash
# Terminal 1: Backend
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2: Frontend
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). You should see the 3D graph. Type a question to explore.

## Project Structure

```
ai-in-aec-kg/
├── frontend/                  # React 19 + TypeScript + Vite
│   ├── src/
│   │   ├── components/        # GraphCanvas, ChatSidebar, NodePopover, etc.
│   │   ├── hooks/             # useChat, useVoice, useGraphData, useSession
│   │   ├── stores/            # Zustand state (appStore.ts)
│   │   ├── lib/               # API client, types, SSE handler
│   │   └── styles/            # Theme colors by node type
│   └── package.json
│
├── backend/
│   ├── app/                   # FastAPI application
│   │   ├── main.py            # App entry, CORS, lifespan
│   │   ├── config.py          # Pydantic settings from .env
│   │   ├── dependencies.py    # Neo4j + OpenAI client singletons
│   │   ├── routers/           # auth, chat, graph, health endpoints
│   │   ├── services/          # Agent graph, tools, chat memory, embeddings, TTS
│   │   └── models/            # Pydantic request/response schemas
│   │
│   ├── data/seed/             # Pre-built graph data (ships with repo)
│   │   ├── *.json             # Pipeline stage outputs
│   │   └── embed_output.json.gz  # Compressed vector embeddings (~17MB)
│   │
│   ├── pipeline/              # Offline graph construction
│   │   ├── run_pipeline.py    # CLI orchestrator (--stage flag)
│   │   ├── seed.py            # Seed loader (no API keys needed)
│   │   ├── parser.py          # Transcript → session objects
│   │   ├── extractor.py       # LLM entity/relationship extraction
│   │   ├── entity_resolution.py  # Fuzzy deduplication
│   │   ├── presentation_extractor.py  # Session → individual presentations
│   │   ├── enrichment.py      # spaCy NER + KeyBERT topics
│   │   ├── embedder.py        # Vector embedding generation + chunking
│   │   ├── loader.py          # Neo4j graph writer
│   │   ├── schema.py          # Neo4j constraints + vector indexes
│   │   └── generate_detailed_summaries.py  # Post-pipeline LLM summaries
│   │
│   ├── tests/                 # pytest test suite
│   └── pyproject.toml         # Python dependencies (uv)
│
├── AI_in_AEC_2026_Snapsight_Summaries.txt  # Source transcript data
├── docker-compose.yml         # Neo4j service
├── .env.example               # Environment variable template
└── CLAUDE.md                  # AI assistant project context
```

## Neo4j Schema

**9 node types**, each with vector indexes for semantic search:

| Node Type | Count | Description |
|-----------|-------|-------------|
| Session | 15 | Conference sessions |
| Presentation | 53 | Individual talks within sessions |
| TranscriptChunk | 278 | ~400-word transcript segments |
| Speaker | 258 | Conference speakers |
| Organization | 431 | Companies, universities, agencies |
| Topic | 660 | Extracted topics and keywords |
| Technology | 121 | Named technologies and tools |
| Concept | 259 | Abstract concepts and ideas |
| Project | 25 | Named projects and initiatives |

**Key relationships:** `PART_OF`, `PRESENTED_BY`, `CHUNK_OF`, `COVERS_TOPIC`, `AFFILIATED_WITH`, `MENTIONS`, `RELATES_TO`, `USES_TECHNOLOGY`, and more.

## Agentic GraphRAG

The chat system uses a [LangGraph](https://langchain-ai.github.io/langgraph/) agent with a ReAct loop — not a static retrieval pipeline. The agent has 6 tools:

| Tool | Purpose |
|------|---------|
| `vector_search_nodes` | Semantic similarity search across node types |
| `get_node_neighbors` | Explore a node's immediate connections |
| `get_node_details` | Fetch full properties of a specific node |
| `expand_subgraph` | Expand seed nodes by N hops |
| `find_paths` | Find shortest paths between two nodes |
| `run_cypher_query` | Execute read-only Cypher for aggregations |

The agent classifies each query into one of three strategies:

- **Entity-navigation** — for questions about specific named entities (*"What presentations are in the Computational Design session?"*) → finds the entity node, then traverses relationships
- **Semantic/exploratory** — for open-ended content questions (*"How is AI being used in structural engineering?"*) → vector search across TranscriptChunks and related types, then explores neighbors
- **Quantitative** — for counts, rankings, or aggregations (*"How many sessions are there?"*) → direct Cypher queries

All reasoning streams to the frontend in real time via SSE, with progressive graph highlighting as nodes are discovered.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Framer Motion, Zustand |
| 3D Graph | [react-force-graph-3d](https://github.com/vasturiano/react-force-graph) + three-spritetext |
| Backend | FastAPI (async), Python 3.12+, uv |
| Agent | LangGraph, langchain-openai |
| Graph DB | Neo4j 5.x Community + APOC |
| LLMs | GPT-4.1 (agent), Gemini 2.5 Flash (extraction) via [OpenRouter](https://openrouter.ai) |
| Embeddings | text-embedding-3-large (3072d) via OpenRouter |
| Voice | Web Speech API (STT), OpenAI TTS with sentence-level streaming pipeline |
| NLP | spaCy, rapidfuzz, KeyBERT |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Status + Neo4j connectivity |
| `GET` | `/api/graph` | Full graph data (nodes + links) |
| `POST` | `/api/register` | Sign up → JWT token |
| `GET` | `/api/session` | Validate token, return user info |
| `POST` | `/api/chat` | Send question → JSON response |
| `POST` | `/api/chat/stream` | Send question → SSE stream with reasoning trace |
| `GET` | `/api/chat/history` | Session message history |
| `GET` | `/api/voice/capabilities` | Check TTS availability |
| `POST` | `/api/voice/tts` | Text → streaming MP3 audio |

## License

MIT
