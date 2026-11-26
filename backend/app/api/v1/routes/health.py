"""
Health Check API Routes

This module defines the FastAPI routes for health checks and monitoring.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, get_async_db
from app.core.health_checks import (
    get_basic_health,
    get_detailed_health,
    get_prometheus_metrics
)

router = APIRouter()


@router.get(
    "",
    summary="Basic health check"
)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns a simple status indicating the API is running.
    """
    return await get_basic_health()


@router.get(
    "/detailed",
    summary="Detailed health check"
)
async def detailed_health_check(db: AsyncSession = Depends(get_async_db)):
    """
    Detailed health check endpoint.
    
    Checks the status of all components (database, vector store, etc.)
    and returns detailed health information.
    """
    return await get_detailed_health(db)


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    response_class=Response,
    responses={
        200: {
            "content": {"text/plain": {}},
            "description": "Prometheus metrics"
        }
    }
)
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for monitoring.
    """
    metrics_text = await get_prometheus_metrics()
    return Response(content=metrics_text, media_type="text/plain")
