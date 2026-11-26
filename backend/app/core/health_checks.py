"""
Health Check Module

This module provides health check functionality for monitoring the application's
components and dependencies.
"""

import logging
import time
import os
import psutil
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text
import httpx

from app.config import settings
from app.db.session import get_db, SessionLocal
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger(__name__)


async def check_database_connection(db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """
    Check database connection health.
    
    Args:
        db: Optional database session
        
    Returns:
        Dict with status and latency
    """
    start_time = time.time()
    status = "healthy"
    error = None
    version = None
    
    try:
        # Use sync session for health check since we're using sync engine
        db_session = SessionLocal()
        try:
            # Execute simple query to check connection
            query = text("SELECT version()")
            result = db_session.execute(query)
            version = result.scalar_one()
        finally:
            db_session.close()
    
    except Exception as e:
        status = "unhealthy"
        error = str(e)
        logger.error(f"Database health check failed: {error}")
    
    latency_ms = round((time.time() - start_time) * 1000, 2)
    
    return {
        "status": status,
        "latency_ms": latency_ms,
        "error": error,
        "version": version
    }


async def check_qdrant_connection() -> Dict[str, Any]:
    """
    Check Qdrant vector store connection health.
    
    Returns:
        Dict with status and latency
    """
    start_time = time.time()
    status = "healthy"
    error = None
    collections = None
    
    try:
        # Create Qdrant client
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY,
            https=settings.QDRANT_USE_HTTPS,
            prefer_grpc=settings.QDRANT_PREFER_GRPC
        )
        
        # List collections to check connection
        collections = client.get_collections().collections
        collections = [c.name for c in collections]
    
    except Exception as e:
        status = "unhealthy"
        error = str(e)
        logger.error(f"Qdrant health check failed: {error}")
    
    latency_ms = round((time.time() - start_time) * 1000, 2)
    
    return {
        "status": status,
        "latency_ms": latency_ms,
        "error": error,
        "collections": collections
    }


async def check_openai_connection() -> Dict[str, Any]:
    """
    Check OpenAI API connection health.
    
    Returns:
        Dict with status and latency
    """
    start_time = time.time()
    status = "healthy"
    error = None
    
    try:
        # Check if API key is configured
        if not settings.OPENAI_API_KEY:
            status = "unhealthy"
            error = "OpenAI API key not configured"
        else:
            # Make a simple request to check connection
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.OPENAI_BASE_URL}/models",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code != 200:
                    status = "unhealthy"
                    error = f"OpenAI API returned status {response.status_code}: {response.text}"
    
    except Exception as e:
        status = "unhealthy"
        error = str(e)
        logger.error(f"OpenAI health check failed: {error}")
    
    latency_ms = round((time.time() - start_time) * 1000, 2)
    
    return {
        "status": status,
        "latency_ms": latency_ms,
        "error": error
    }


async def check_system_resources() -> Dict[str, Any]:
    """
    Check system resources (CPU, memory, disk).
    
    Returns:
        Dict with system resource metrics
    """
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    
    # Memory usage
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    memory_used_mb = memory.used / (1024 * 1024)
    memory_total_mb = memory.total / (1024 * 1024)
    
    # Disk usage
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent
    disk_used_gb = disk.used / (1024 * 1024 * 1024)
    disk_total_gb = disk.total / (1024 * 1024 * 1024)
    
    # Process info
    process = psutil.Process(os.getpid())
    process_memory_mb = process.memory_info().rss / (1024 * 1024)
    process_cpu_percent = process.cpu_percent(interval=0.1)
    process_threads = process.num_threads()
    
    return {
        "cpu": {
            "percent": round(cpu_percent, 2)
        },
        "memory": {
            "percent": round(memory_percent, 2),
            "used_mb": round(memory_used_mb, 2),
            "total_mb": round(memory_total_mb, 2)
        },
        "disk": {
            "percent": round(disk_percent, 2),
            "used_gb": round(disk_used_gb, 2),
            "total_gb": round(disk_total_gb, 2)
        },
        "process": {
            "memory_mb": round(process_memory_mb, 2),
            "cpu_percent": round(process_cpu_percent, 2),
            "threads": process_threads
        }
    }


async def get_basic_health() -> Dict[str, str]:
    """
    Get basic health status.
    
    Returns:
        Dict with status
    """
    return {"status": "ok"}


async def get_detailed_health(db: AsyncSession) -> Dict[str, Any]:
    """
    Get detailed health status of all components.
    
    Args:
        db: Database session
        
    Returns:
        Dict with detailed health status
    """
    # Run all health checks concurrently
    db_check, qdrant_check, openai_check, system_check = await asyncio.gather(
        check_database_connection(db),
        check_qdrant_connection(),
        check_openai_connection(),
        check_system_resources()
    )
    
    # Determine overall status
    overall_status = "healthy"
    if db_check["status"] == "unhealthy" or qdrant_check["status"] == "unhealthy":
        overall_status = "unhealthy"
    
    # Build response
    return {
        "status": overall_status,
        "timestamp": time.time(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "components": {
            "database": db_check,
            "qdrant": qdrant_check,
            "openai": openai_check
        },
        "system": system_check
    }


async def get_prometheus_metrics() -> str:
    """
    Get Prometheus metrics.
    
    Returns:
        Prometheus metrics in text format
    """
    # Run health checks
    db_check = await check_database_connection()
    qdrant_check = await check_qdrant_connection()
    system_check = await check_system_resources()
    
    # Format metrics in Prometheus text format
    metrics = []
    
    # Component status metrics (0 = unhealthy, 1 = healthy)
    metrics.append("# HELP component_status Status of each component (0 = unhealthy, 1 = healthy)")
    metrics.append("# TYPE component_status gauge")
    metrics.append(f"component_status{{component=\"database\"}} {1 if db_check['status'] == 'healthy' else 0}")
    metrics.append(f"component_status{{component=\"qdrant\"}} {1 if qdrant_check['status'] == 'healthy' else 0}")
    
    # Latency metrics
    metrics.append("# HELP component_latency_ms Latency of each component in milliseconds")
    metrics.append("# TYPE component_latency_ms gauge")
    metrics.append(f"component_latency_ms{{component=\"database\"}} {db_check['latency_ms']}")
    metrics.append(f"component_latency_ms{{component=\"qdrant\"}} {qdrant_check['latency_ms']}")
    
    # System metrics
    metrics.append("# HELP system_cpu_percent CPU usage percentage")
    metrics.append("# TYPE system_cpu_percent gauge")
    metrics.append(f"system_cpu_percent {system_check['cpu']['percent']}")
    
    metrics.append("# HELP system_memory_percent Memory usage percentage")
    metrics.append("# TYPE system_memory_percent gauge")
    metrics.append(f"system_memory_percent {system_check['memory']['percent']}")
    
    metrics.append("# HELP system_memory_used_mb Memory used in MB")
    metrics.append("# TYPE system_memory_used_mb gauge")
    metrics.append(f"system_memory_used_mb {system_check['memory']['used_mb']}")
    
    metrics.append("# HELP system_disk_percent Disk usage percentage")
    metrics.append("# TYPE system_disk_percent gauge")
    metrics.append(f"system_disk_percent {system_check['disk']['percent']}")
    
    metrics.append("# HELP process_memory_mb Process memory usage in MB")
    metrics.append("# TYPE process_memory_mb gauge")
    metrics.append(f"process_memory_mb {system_check['process']['memory_mb']}")
    
    metrics.append("# HELP process_cpu_percent Process CPU usage percentage")
    metrics.append("# TYPE process_cpu_percent gauge")
    metrics.append(f"process_cpu_percent {system_check['process']['cpu_percent']}")
    
    metrics.append("# HELP process_threads Process thread count")
    metrics.append("# TYPE process_threads gauge")
    metrics.append(f"process_threads {system_check['process']['threads']}")
    
    return "\n".join(metrics)


async def run_startup_health_checks() -> Dict[str, Any]:
    """
    Run comprehensive health checks during application startup.
    
    Returns:
        Dict with health check results for all critical services
    """
    logger.info("Running startup health checks...")
    
    # Run all health checks concurrently
    db_check, qdrant_check, openai_check, system_check = await asyncio.gather(
        check_database_connection(),
        check_qdrant_connection(),
        check_openai_connection(),
        check_system_resources()
    )
    
    # Determine overall status
    overall_status = "healthy"
    if db_check["status"] == "unhealthy" or qdrant_check["status"] == "unhealthy":
        overall_status = "unhealthy"
    
    # Build comprehensive results
    results = {
        "overall_status": overall_status,
        "timestamp": time.time(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": {
            "status": db_check["status"],
            "latency_ms": db_check["latency_ms"],
            "success": db_check["status"] == "healthy",
            "error": db_check.get("error"),
            "version": db_check.get("version")
        },
        "qdrant": {
            "status": qdrant_check["status"],
            "latency_ms": qdrant_check["latency_ms"],
            "success": qdrant_check["status"] == "healthy",
            "error": qdrant_check.get("error"),
            "collections": qdrant_check.get("collections", [])
        },
        "openai": {
            "status": openai_check["status"],
            "latency_ms": openai_check["latency_ms"],
            "success": openai_check["status"] == "healthy",
            "error": openai_check.get("error")
        },
        "embedding": {
            "status": "healthy",  # Assume healthy if OpenAI is healthy
            "latency_ms": openai_check["latency_ms"],
            "success": openai_check["status"] == "healthy",
            "error": openai_check.get("error")
        },
        "system": system_check
    }
    
    # Log results
    if overall_status == "healthy":
        logger.info("All startup health checks passed")
    else:
        logger.warning(f"Some startup health checks failed: {overall_status}")
    
    return results