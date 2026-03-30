from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies import (
    close_neo4j_driver,
    init_neo4j_driver,
    init_openai_client,
    init_tts_client,
)
from app.routers import chat, graph, health, voice


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    # Startup
    await init_neo4j_driver()
    init_openai_client()
    init_tts_client()
    yield
    # Shutdown
    await close_neo4j_driver()


app = FastAPI(
    title="AI in AEC Knowledge Graph",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
settings = get_settings()
origins = [
    settings.APP_URL,
    "http://localhost:5173",
]
# De-duplicate while keeping order
origins = list(dict.fromkeys(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(graph.router)
app.include_router(chat.router)
app.include_router(voice.router)
