from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    id: str
    label: str
    name: str
    group: str = ""
    properties: dict = {}


class GraphLink(BaseModel):
    source: str
    target: str
    type: str
    properties: dict = {}


class GraphData(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str
    email: str
    company: str


class RegisterResponse(BaseModel):
    session_id: str
    token: str


class UserInfo(BaseModel):
    name: str
    email: str
    company: str


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


class ChatMessage(BaseModel):
    role: str
    content: str


class SubgraphHighlight(BaseModel):
    node_ids: list[str] = []
    link_ids: list[str] = []


class ChatResponse(BaseModel):
    answer: str
    subgraph: SubgraphHighlight
    sources: list[dict] = []
