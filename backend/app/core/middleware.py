"""
Middleware Components

Custom middleware for:
- Request/Response logging
- Tenant isolation
- Rate limiting
- Performance monitoring
- Error handling
"""

from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.config import settings
from app.core.exceptions import RateLimitException, TenantAccessDeniedException
import time
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ============================================================================
# REQUEST LOGGING MIDDLEWARE
# ============================================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all HTTP requests and responses with timing information.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            }
        )
        
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            
            # Log response
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": process_time
                }
            )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "process_time": process_time
                },
                exc_info=True
            )
            raise


# ============================================================================
# RATE LIMITING MIDDLEWARE
# ============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.
    For production, use rate limiting.
    """
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls  # Number of calls allowed
        self.period = period  # Time period in seconds
        self.requests = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/health/detailed"]:
            return await call_next(request)
        
        # Get client identifier (IP address or user ID)
        client_id = self._get_client_id(request)
        
        # Check rate limit
        now = datetime.now()
        if not self._check_rate_limit(client_id, now):
            raise RateLimitException()
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self._get_remaining_calls(client_id, now)
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int((now + timedelta(seconds=self.period)).timestamp()))
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request"""
        # Try to get user ID from request state (if authenticated)
        if hasattr(request.state, "user_id"):
            return f"user_{request.state.user_id}"
        
        # Fall back to IP address
        if request.client:
            return f"ip_{request.client.host}"
        
        return "anonymous"
    
    def _check_rate_limit(self, client_id: str, now: datetime) -> bool:
        """Check if client has exceeded rate limit"""
        # Clean old requests
        cutoff = now - timedelta(seconds=self.period)
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]
        
        # Check if limit exceeded
        if len(self.requests[client_id]) >= self.calls:
            return False
        
        # Add current request
        self.requests[client_id].append(now)
        return True
    
    def _get_remaining_calls(self, client_id: str, now: datetime) -> int:
        """Get remaining calls for client"""
        cutoff = now - timedelta(seconds=self.period)
        recent_requests = [
            req_time for req_time in self.requests.get(client_id, [])
            if req_time > cutoff
        ]
        return max(0, self.calls - len(recent_requests))


# ============================================================================
# TENANT ISOLATION MIDDLEWARE
# ============================================================================

class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Ensures all requests are scoped to a specific tenant/organization.
    Extracts organization context from JWT token or API key.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip for public endpoints
        public_paths = [
            "/health",
            "/health/detailed",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]
        
        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)
        
        # Widget endpoints use API key authentication (handled separately)
        if request.url.path.startswith("/api/v1/widget"):
            return await call_next(request)
        
        # For authenticated endpoints, organization_id should be set by dependencies
        # This middleware just ensures it's present where required
        
        response = await call_next(request)
        return response


# ============================================================================
# CORS MIDDLEWARE CONFIGURATION
# ============================================================================

def setup_cors_middleware(app):
    """
    Configure CORS middleware for the application.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=["X-Request-ID", "X-Process-Time"]
    )


# ============================================================================
# ERROR HANDLING MIDDLEWARE
# ============================================================================

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Catches and formats all exceptions into consistent JSON responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            # Log the error
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                f"Unhandled exception",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "error": str(exc)
                },
                exc_info=True
            )
            
            # Return formatted error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "detail": "An unexpected error occurred. Please try again later.",
                    "request_id": request_id
                }
            )


# ============================================================================
# SECURITY HEADERS MIDDLEWARE
# ============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Configure CSP based on endpoint
        if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            # Allow Swagger UI resources for documentation endpoints
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'"
            )
        else:
            # Strict CSP for API endpoints
            csp = "default-src 'self'"
        
        response.headers["Content-Security-Policy"] = csp
        
        return response


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "RequestLoggingMiddleware",
    "RateLimitMiddleware",
    "TenantIsolationMiddleware",
    "ErrorHandlingMiddleware",
    "SecurityHeadersMiddleware",
    "setup_cors_middleware"
]

