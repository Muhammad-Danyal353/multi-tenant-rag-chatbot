"""
Main FastAPI Application

This is the entry point for the SaaS RAG Chatbot backend application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import settings
from app.core.middlewares import (
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    TenantIsolationMiddleware,
    ErrorHandlingMiddleware,
    SecurityHeadersMiddleware,
    setup_cors_middleware
)
from app.core.exceptions import BaseAPIException
import logging
from app.core.logging import setup_logging

# Configure logging
setup_logging()

# logging.basicConfig(
#     level=getattr(logging, settings.LOG_LEVEL),
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(sys.__stdout__)
#     ]
# )
# logging.raiseExceptions = False

logger = logging.getLogger(__name__)


# ============================================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================================



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context: runs setup on startup and cleanup on shutdown.
    """
    # --- Startup logic ---
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Run comprehensive health checks
    try:
        logger.info("Running without startup health checks for just now...")
        pass
        # from app.core.health_checks import run_startup_health_checks
        # health_results = await run_startup_health_checks()
        
        # # Check if critical services are healthy
        # critical_services = ["database", "qdrant", "openai", "embedding"]
        # critical_failures = [
        #     service for service in critical_services 
        #     if service in health_results and not health_results[service]["success"]
        # ]
        
        # if critical_failures:
        #     logger.error(f"Critical services failed: {', '.join(critical_failures)}")
        #     logger.error("Application may not function correctly!")
        # else:
        #     logger.info("All critical services are healthy - application ready!")
            
    except Exception as e:
        logger.error(f"Startup health checks failed: {str(e)}")
        logger.error("Proceeding without health checks - application may not function correctly!")

    # Initialize Qdrant service and create default collection
    try:
        from app.services.qdrant_service import get_qdrant_service
        qdrant_service = get_qdrant_service()
        
        logger.info("Creating Qdrant Collection")
        qdrant_service.create_collection(settings.QDRANT_DEFAULT_COLLECTION_NAME, True)
        logger.info(f"Qdrant Collection {settings.QDRANT_DEFAULT_COLLECTION_NAME} created successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant service: {str(e)}")
        logger.warning("Application will continue without Qdrant (some features may not work)")

    # Log configuration
    logger.info(f"Multi-tenancy enabled: {settings.ENABLE_MULTI_TENANCY}")
    logger.info(f"Email verification enabled: {settings.ENABLE_EMAIL_VERIFICATION}")
    logger.info(f"Analytics enabled: {settings.ENABLE_ANALYTICS}")
    logger.info("Application startup complete")

    # Yield control to the app (app runs here)
    yield

    # --- Shutdown logic ---
    logger.info("Shutting down application...")
    # Add cleanup tasks here (close connections, etc.)
    logger.info("Application shutdown complete")


# ============================================================================
# CREATE FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-tenant SaaS RAG Chatbot Platform - Beat DocuChat.io with superior UX and performance",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(BaseAPIException)
async def custom_exception_handler(request: Request, exc: BaseAPIException):
    """
    Handle custom API exceptions.
    """
    logger.warning(
        f"API Exception: {exc.detail}",
        extra={
            "path": request.url.path,
            "error_code": exc.error_code,
            "status_code": exc.status_code
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.error_code or "ERROR",
            "message": exc.detail,
            "status_code": exc.status_code
        },
        headers=exc.headers
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle standard HTTP exceptions.
    """
    logger.warning(
        f"HTTP Exception: {exc.detail}",
        extra={
            "path": request.url.path,
            "status_code": exc.status_code
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors (Pydantic validation).
    """
    logger.warning(
        f"Validation Error",
        extra={
            "path": request.url.path,
            "errors": exc.errors()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors(),
            "status_code": 422
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle all unhandled exceptions.
    """
    logger.error(
        f"Unhandled Exception: {str(exc)}",
        extra={"path": request.url.path},
        exc_info=True
    )
    
    # Don't expose internal errors in production
    detail = str(exc) if settings.DEBUG else "An internal error occurred"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "INTERNAL_SERVER_ERROR",
            "message": detail,
            "status_code": 500
        }
    )


# ============================================================================
# MIDDLEWARE SETUP
# ============================================================================

# Security headers (applied first)
app.add_middleware(SecurityHeadersMiddleware)

# CORS configuration
setup_cors_middleware(app)

# Request logging
if settings.ENABLE_REQUEST_LOGGING:
    app.add_middleware(RequestLoggingMiddleware)

# Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    calls=settings.RATE_LIMIT_PER_MINUTE,
    period=60
)

# Tenant isolation
if settings.ENABLE_MULTI_TENANCY:
    app.add_middleware(TenantIsolationMiddleware)

# Domain validation for widget endpoints
from app.core.middlewares.domain_validation import DomainValidationMiddleware
app.add_middleware(DomainValidationMiddleware)

# Error handling
app.add_middleware(ErrorHandlingMiddleware)



# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 if application is running.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """
    Detailed health check with component status.
    """
    from app.db.session import check_db_connection
    
    db_healthy = check_db_connection()
    
    # Check Qdrant health
    qdrant_healthy = False
    try:
        from app.services.qdrant_service import get_qdrant_service
        qdrant_service = get_qdrant_service()
        qdrant_healthy = qdrant_service.test_connection()
    except Exception as e:
        logger.error(f"Qdrant health check failed: {str(e)}")
    
    
    overall_status = "healthy" if (db_healthy and qdrant_healthy) else "unhealthy"
    
    return {
        "status": overall_status,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "components": {
            "database": "healthy" if db_healthy else "unhealthy",
            "qdrant": "healthy" if qdrant_healthy else "unhealthy",
            "api": "healthy"
        }
    }


@app.get("/health/qdrant", tags=["Health"])
async def qdrant_health_check():
    """
    Qdrant-specific health check.
    """
    try:
        from app.services.qdrant_service import get_qdrant_service
        qdrant_service = get_qdrant_service()
        
        # Test connection
        is_healthy = qdrant_service.test_connection()
        
        if is_healthy:
            # Get collection info
            collections = qdrant_service.list_collections()
            
            return {
                "status": "healthy",
                "service": "qdrant",
                "collections_count": len(collections),
                "collections": collections[:10],  # Show first 10 collections
                "timestamp": "2024-01-01T00:00:00Z"
            }
        else:
            return {
                "status": "unhealthy",
                "service": "qdrant",
                "error": "Connection test failed",
                "timestamp": "2024-01-01T00:00:00Z"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "service": "qdrant",
            "error": str(e),
            "timestamp": "2024-01-01T00:00:00Z"
        }


@app.get("/health/metrics", tags=["Health"])
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for monitoring.
    """
    try:
        from app.core.health_checks import get_prometheus_metrics
        metrics_text = await get_prometheus_metrics()
        from fastapi import Response
        return Response(content=metrics_text, media_type="text/plain")
    except Exception as e:
        logger.error(f"Failed to get metrics: {str(e)}")
        return Response(content="# Error getting metrics\n", media_type="text/plain")


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Multi-tenant SaaS RAG Chatbot Platform",
        "docs": "/docs" if settings.DEBUG else None,
        "api_v1": settings.API_V1_PREFIX,
        "status": "running"
    }


@app.get("/test", tags=["Test"])
async def test_endpoint():
    """
    Simple test endpoint to verify API is working.
    """
    return {
        "message": "API is working correctly!",
        "timestamp": "2024-01-01T00:00:00Z",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "api_v1": settings.API_V1_PREFIX
        }
    }


# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

# Import and register API routers
try:
    from app.api.v1 import api_router

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    logger.info("All API routers registered successfully")
    
except ImportError as e:
    logger.error(f"Failed to import API routers: {str(e)}")
    logger.info("Running with basic endpoints only")


# ============================================================================
# MAIN ENTRY POINT (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        # reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower()
    )

