"""
Domain Validation Middleware

Validates that widget requests are coming from allowed domains.
"""

from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from urllib.parse import urlparse
import logging

from app.services.api_key_service import APIKeyService
from app.services.domain_allowlist_service import DomainAllowlistService
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

class DomainValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates if widget requests are coming from allowed domains.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only check domain for widget endpoints
        if not request.url.path.startswith("/api/v1/widget"):
            return await call_next(request)
        
        # Get API key from request
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "API key is required for widget access"}
            )
        
        # Get referer domain
        referer = request.headers.get("Referer")
        if not referer:
            logger.warning(f"Widget request without referer header: {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"error": "Referer header is required for widget access"}
            )
        
        try:
            # Extract domain from referer
            parsed_url = urlparse(referer)
            request_domain = parsed_url.netloc
            
            # Remove port if present
            if ":" in request_domain:
                request_domain = request_domain.split(":")[0]
            
            # Get bot from API key
            async with get_db_session() as db:
                api_key_service = APIKeyService(db)
                bot = await api_key_service.validate_api_key(api_key)
                
                if not bot:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid API key"}
                    )
                
                # Check if domain is allowed
                domain_service = DomainAllowlistService(db)
                is_allowed = await domain_service.is_domain_allowed(bot.id, request_domain)
                
                if not is_allowed:
                    logger.warning(
                        f"Domain access denied",
                        extra={
                            "bot_id": bot.id,
                            "domain": request_domain,
                            "path": request.url.path
                        }
                    )
                    return JSONResponse(
                        status_code=403,
                        content={"error": f"Domain '{request_domain}' is not allowed to access this widget"}
                    )
                
                # Set bot context for request handlers
                request.state.bot_id = bot.id
                request.state.organization_id = bot.organization_id
                
                return await call_next(request)
                
        except Exception as e:
            logger.error(
                f"Domain validation error",
                extra={
                    "error": str(e),
                    "path": request.url.path
                },
                exc_info=True
            )
            return JSONResponse(
                status_code=500,
                content={"error": "An error occurred while validating domain access"}
            )
