"""
Middleware Package

This package contains middleware components for the application.
"""

from app.core.middlewares.usage_limiter import (
    usage_limiter, check_resource_limit, track_usage
)

# Import middleware classes from the parent middleware module
from ..middleware import (
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    TenantIsolationMiddleware,
    ErrorHandlingMiddleware,
    SecurityHeadersMiddleware,
    setup_cors_middleware
)

# Import domain validation middleware
from app.core.middlewares.domain_validation import DomainValidationMiddleware

# Export all middleware components
__all__ = [
    "usage_limiter",
    "check_resource_limit",
    "track_usage",
    "RequestLoggingMiddleware",
    "RateLimitMiddleware",
    "TenantIsolationMiddleware",
    "ErrorHandlingMiddleware",
    "SecurityHeadersMiddleware",
    "setup_cors_middleware",
    "DomainValidationMiddleware"
]
