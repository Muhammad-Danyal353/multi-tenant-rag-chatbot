"""
Usage Limiter Middleware

This middleware enforces usage limits based on subscription plans.
"""

import logging
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, get_async_db
from app.services.usage_service import get_usage_service, UsageService
from app.core.dependencies import get_current_organization_id
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class UsageLimiterMiddleware:
    """
    Middleware to enforce usage limits based on subscription plans.
    """
    
    def __init__(self):
        """Initialize the middleware."""
        self.usage_service = get_usage_service()
    
    async def check_limit(
        self, 
        request: Request, 
        limit_type: str,
        db: AsyncSession = Depends(get_async_db)
    ) -> None:
        """
        Check if a resource limit has been reached.
        
        Args:
            request: FastAPI request
            limit_type: Type of limit to check (bots, knowledge_sources, etc.)
            db: Database session
            
        Raises:
            HTTPException: If the limit has been reached
        """
        # Get organization ID from request state
        organization_id = await get_current_organization_id(request)
        
        if not organization_id:
            # No organization context, skip limit check
            return
        
        # Check limit
        limit_reached, current_count, limit = await self.usage_service.check_limit(
            organization_id, limit_type, db
        )
        
        if limit_reached:
            logger.warning(
                f"Usage limit reached for {organization_id}: {limit_type} "
                f"({current_count}/{limit})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Usage limit reached for {limit_type}. "
                       f"Current usage: {current_count}/{limit}. "
                       f"Please upgrade your subscription plan."
            )
    
    async def increment_usage(
        self,
        request: Request,
        metric_type: str,
        amount: int = 1,
        db: AsyncSession = Depends(get_async_db)
    ) -> bool:
        """
        Increment a usage counter.
        
        Args:
            request: FastAPI request
            metric_type: Type of metric to increment (messages, storage_mb, etc.)
            amount: Amount to increment
            db: Database session
            
        Returns:
            True if successful, False if limit exceeded
        """
        # Get organization ID from request state
        organization_id = await get_current_organization_id(request)
        
        if not organization_id:
            # No organization context, skip increment
            return True
        
        # Increment usage
        return await self.usage_service.increment_usage(
            organization_id, metric_type, amount, db
        )


# Singleton instance
usage_limiter = UsageLimiterMiddleware()


def check_resource_limit(limit_type: str) -> Callable:
    """
    Dependency to check if a resource limit has been reached.
    
    Args:
        limit_type: Type of limit to check (bots, knowledge_sources, etc.)
        
    Returns:
        Dependency function
    """
    async def dependency(
        request: Request,
        db: AsyncSession = Depends(get_async_db)
    ) -> None:
        await usage_limiter.check_limit(request, limit_type, db)
    
    return dependency


def track_usage(metric_type: str, amount: int = 1) -> Callable:
    """
    Dependency to track usage.
    
    Args:
        metric_type: Type of metric to track (messages, storage_mb, etc.)
        amount: Amount to increment
        
    Returns:
        Dependency function
    """
    async def dependency(
        request: Request,
        db: AsyncSession = Depends(get_async_db)
    ) -> None:
        success = await usage_limiter.increment_usage(request, metric_type, amount, db)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Usage limit exceeded for {metric_type}. "
                       f"Please upgrade your subscription plan."
            )
    
    return dependency
