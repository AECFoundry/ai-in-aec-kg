from __future__ import annotations

from fastapi import APIRouter, Depends
from neo4j import AsyncDriver

from app.dependencies import get_neo4j_driver
from app.services.neo4j_queries import check_connectivity

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check(
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> dict:
    neo4j_ok = await check_connectivity(driver)
    return {
        "status": "ok" if neo4j_ok else "degraded",
        "neo4j": "connected" if neo4j_ok else "unreachable",
    }
