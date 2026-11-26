"""
Usage Service for Tracking Resource Usage

This module handles tracking and enforcing resource usage limits
based on subscription plans.
"""

import logging
from typing import Dict, Optional, Any, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, func
from datetime import datetime, timedelta

from app.config import settings
from app.db.models.organization import Organization
from app.db.models.subscription import Subscription, UsageCounter
from app.db.models.bot import Bot
from app.db.models.knowledge_base import KnowledgeSource

logger = logging.getLogger(__name__)


class UsageService:
    """
    Service for tracking and enforcing resource usage limits.
    """
    
    def __init__(self):
        """Initialize the usage service."""
        # Plan limits from settings
        self.plan_limits = {
            "free": settings.FREE_PLAN_LIMITS,
            "pro": settings.PRO_PLAN_LIMITS,
            "enterprise": settings.ENTERPRISE_PLAN_LIMITS
        }
    
    async def get_organization_usage(self, organization_id: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Get current usage metrics for an organization.
        
        Args:
            organization_id: Organization ID
            db: Database session
            
        Returns:
            Dict with usage metrics and limits
        """
        # Get organization with subscription
        stmt = select(Organization).where(Organization.id == organization_id)
        result = await db.execute(stmt)
        organization = result.scalar_one_or_none()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization with ID {organization_id} not found"
            )
        
        # Get plan limits
        plan = organization.subscription_plan or "free"
        plan_limits = self.plan_limits.get(plan, self.plan_limits["free"])
        
        # Get usage counters
        stmt = select(UsageCounter).where(UsageCounter.organization_id == organization_id)
        result = await db.execute(stmt)
        usage_counters =  result.scalars().all()
        
        # Create usage counter map
        usage_map = {counter.metric_type: counter.count for counter in usage_counters}
        
        # Get bot count
        stmt = select(func.count(Bot.id)).where(
            Bot.organization_id == organization_id,
            Bot.deleted_at.is_(None)
        )
        result = await db.execute(stmt)
        bot_count = result.scalar_one() or 0
        
        # Get knowledge source count
        stmt = select(func.count(KnowledgeSource.id)).where(
            KnowledgeSource.organization_id == organization_id
        )
        result = await db.execute(stmt)
        knowledge_source_count = result.scalar_one() or 0
        
        # Calculate storage usage (in MB)
        storage_usage = usage_map.get("storage_mb", 0)
        
        # Get message count for current period
        message_count = usage_map.get("messages", 0)
        
        # Format response
        return {
            "plan": plan,
            "messages": {
                "used": message_count,
                "limit": plan_limits.get("max_messages_per_month", 0)
            },
            "storage": {
                "used": storage_usage,
                "limit": plan_limits.get("max_storage_mb", 0)
            },
            "bots": {
                "used": bot_count,
                "limit": plan_limits.get("max_bots", 0)
            },
            "knowledge_sources": {
                "used": knowledge_source_count,
                "limit": plan_limits.get("max_knowledge_sources", 0)
            }
        }
    
    async def increment_usage(
        self, organization_id: str, metric_type: str, amount: int, db: AsyncSession
    ) -> bool:
        """
        Increment a usage counter for an organization.
        
        Args:
            organization_id: Organization ID
            metric_type: Type of metric (messages, storage_mb, etc.)
            amount: Amount to increment
            db: Database session
            
        Returns:
            True if successful, False if limit exceeded
        """
        # Get organization with subscription
        stmt = select(Organization).where(Organization.id == organization_id)
        result = await db.execute(stmt)
        organization = result.scalar_one_or_none()
        
        if not organization:
            logger.error(f"Organization with ID {organization_id} not found")
            return False
        
        # Get plan limits
        plan = organization.subscription_plan or "free"
        plan_limits = self.plan_limits.get(plan, self.plan_limits["free"])
        
        # Get current usage counter
        stmt = select(UsageCounter).where(
            UsageCounter.organization_id == organization_id,
            UsageCounter.metric_type == metric_type
        )
        result = await db.execute(stmt)
        counter = result.scalar_one_or_none()
        
        # Get current period
        now = datetime.utcnow()
        period_start = datetime(now.year, now.month, 1).isoformat()
        next_month = now.month + 1 if now.month < 12 else 1
        next_year = now.year + 1 if now.month == 12 else now.year
        period_end = datetime(next_year, next_month, 1).isoformat()
        
        # Create counter if it doesn't exist
        if not counter:
            counter = UsageCounter(
                organization_id=organization_id,
                metric_type=metric_type,
                count=0,
                period_start=period_start,
                period_end=period_end,
                reset_at=period_end
            )
            db.add(counter)
        
        # Check if counter needs to be reset (new period)
        if counter.period_end and counter.period_end < now.isoformat():
            counter.count = 0
            counter.period_start = period_start
            counter.period_end = period_end
            counter.reset_at = period_end
        
        # Check if increment would exceed limit
        limit_key = None
        if metric_type == "messages":
            limit_key = "max_messages_per_month"
        elif metric_type == "storage_mb":
            limit_key = "max_storage_mb"
        
        if limit_key and limit_key in plan_limits:
            limit = plan_limits[limit_key]
            # -1 means unlimited
            if limit != -1 and counter.count + amount > limit:
                # Limit would be exceeded
                logger.warning(
                    f"Usage limit exceeded for {organization_id}: {metric_type} "
                    f"({counter.count}/{limit})"
                )
                return False
        
        # Increment counter
        counter.count += amount
        counter.updated_at = now
        
        await db.commit()
        return True
    
    async def check_limit(
        self, organization_id: str, limit_type: str, db: AsyncSession
    ) -> Tuple[bool, int, int]:
        """
        Check if an organization has reached a resource limit.
        
        Args:
            organization_id: Organization ID
            limit_type: Type of limit (bots, knowledge_sources, etc.)
            db: Database session
            
        Returns:
            Tuple of (has_limit, current_count, limit)
        """
        # Get organization with subscription
        stmt = select(Organization).where(Organization.id == organization_id)
        result = await db.execute(stmt)
        organization = result.scalar_one_or_none()
        
        if not organization:
            logger.error(f"Organization with ID {organization_id} not found")
            return (False, 0, 0)
        
        # Get plan limits
        plan = organization.subscription_plan or "free"
        plan_limits = self.plan_limits.get(plan, self.plan_limits["free"])
        
        # Get current count
        current_count = 0
        limit = 0
        
        if limit_type == "bots":
            # Count active bots
            stmt = select(func.count(Bot.id)).where(
                Bot.organization_id == organization_id,
                Bot.deleted_at.is_(None)
            )
            result = await db.execute(stmt)
            current_count = result.scalar_one() or 0
            limit = plan_limits.get("max_bots", 0)
        
        elif limit_type == "knowledge_sources":
            # Count knowledge sources
            stmt = select(func.count(KnowledgeSource.id)).where(
                KnowledgeSource.organization_id == organization_id
            )
            result = await db.execute(stmt)
            current_count = result.scalar_one() or 0
            limit = plan_limits.get("max_knowledge_sources", 0)
        
        # Check if limit reached
        # -1 means unlimited
        if limit == -1:
            return (False, current_count, limit)
        
        return (current_count >= limit, current_count, limit)


# Singleton instance
usage_service = UsageService()


def get_usage_service() -> UsageService:
    """
    Dependency injection helper for FastAPI routes.
    Returns the global usage service instance.
    """
    return usage_service
