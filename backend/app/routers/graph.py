from __future__ import annotations

from fastapi import APIRouter, Depends
from neo4j import AsyncDriver

from app.dependencies import get_neo4j_driver
from app.models.schemas import GraphData, GraphLink, GraphNode
from app.services.neo4j_queries import get_full_graph

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph", response_model=GraphData)
async def fetch_graph(
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> GraphData:
    """Return every node and relationship in the knowledge graph."""
    raw = await get_full_graph(driver)

    nodes = [
        GraphNode(
            id=n["id"],
            label=n["label"],
            name=n["name"],
            group=n["label"],
            properties=n["properties"],
        )
        for n in raw["nodes"]
    ]

    links = [
        GraphLink(
            source=link["source"],
            target=link["target"],
            type=link["type"],
            properties=link["properties"],
        )
        for link in raw["links"]
    ]

    return GraphData(nodes=nodes, links=links)
