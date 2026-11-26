"""
Checkout Service for Lemon Squeezy Integration

This module handles checkout link generation and subscription management
using the Lemon Squeezy API.
"""

import logging
from typing import Dict, Optional, Any, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from datetime import datetime

from app.config import settings
from app.db.models.organization import Organization
from app.db.models.subscription import Subscription, Plan
from app.services.billing_service import get_billing_service, BillingService
from app.schemas.billing import CheckoutSessionCreate

logger = logging.getLogger(__name__)


class CheckoutService:
    """
    Service for managing checkout sessions and subscriptions.
    """
    
    def __init__(self, billing_service: BillingService):
        """Initialize with billing service."""
        self.billing_service = billing_service
    
    async def create_checkout_session(
        self, data: CheckoutSessionCreate, user_id: str, user_email: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Create a checkout session for a subscription plan.
        
        Args:
            data: Checkout session data
            user_id: ID of the user creating the checkout
            user_email: Email of the user
            db: Database session
            
        Returns:
            Dict with checkout URL and ID
        """
        # Validate organization exists
        stmt = select(Organization).where(Organization.id == data.organization_id)
        result = await db.execute(stmt)
        organization = result.scalar_one_or_none()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization with ID {data.organization_id} not found"
            )
        
        # Get variant ID for the plan
        variant_id = self.billing_service.plan_to_variant.get(data.plan_id)
        if not variant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan ID: {data.plan_id}"
            )
        
        # Create custom data for the checkout
        custom_data = {
            "organization_id": data.organization_id,
            "user_id": user_id
        }
        
        # Create checkout session
        try:
            checkout = await self.billing_service.create_checkout(
                variant_id=variant_id,
                user_email=user_email,
                custom_data=custom_data
            )
            
            return checkout
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create checkout session"
            )
    
    async def get_subscription(self, organization_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Get subscription details for an organization.
        
        Args:
            organization_id: Organization ID
            db: Database session
            
        Returns:
            Subscription details or None if not found
        """
        # Query the subscription
        stmt = select(Subscription).where(Subscription.organization_id == organization_id)
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            return None
        
        # Get plan details
        stmt = select(Plan).where(Plan.id == subscription.plan_id)
        result = await db.execute(stmt)
        plan = result.scalar_one_or_none()
        
        # Format response
        return {
            "id": subscription.id,
            "organization_id": subscription.organization_id,
            "plan_id": subscription.plan_id,
            "plan_name": plan.name if plan else None,
            "status": subscription.status,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "trial_end": subscription.trial_end,
            "cancel_at_period_end": subscription.cancel_at_period_end == "true",
            "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
            "updated_at": subscription.updated_at.isoformat() if subscription.updated_at else None
        }
    
    async def cancel_subscription(self, organization_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Cancel a subscription for an organization.
        
        Args:
            organization_id: Organization ID
            db: Database session
            
        Returns:
            Updated subscription details or None if not found
        """
        # Query the subscription
        stmt = select(Subscription).where(Subscription.organization_id == organization_id)
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active subscription found for organization {organization_id}"
            )
        
        # Check if subscription can be cancelled
        if subscription.status in ["cancelled", "expired"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription is already cancelled or expired"
            )
        
        # Cancel subscription in Lemon Squeezy
        if subscription.lemonsqueezy_subscription_id:
            try:
                await self.billing_service.cancel_subscription(subscription.lemonsqueezy_subscription_id)
            except Exception as e:
                logger.error(f"Error cancelling subscription: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to cancel subscription"
                )
        
        # Update subscription in database
        subscription.status = "cancelled"
        subscription.cancel_at_period_end = "true"
        subscription.cancelled_at = datetime.utcnow().isoformat()
        subscription.updated_at = datetime.utcnow()
        
        # Update organization
        stmt = select(Organization).where(Organization.id == organization_id)
        result = await db.execute(stmt)
        organization = result.scalar_one_or_none()
        
        if organization:
            organization.subscription_status = "cancelled"
        
        await db.commit()
        
        # Return updated subscription
        return await self.get_subscription(organization_id, db)
    
    async def list_plans(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        List all available subscription plans.
        
        Args:
            db: Database session
            
        Returns:
            List of plans
        """
        # Query all active plans
        stmt = select(Plan).where(Plan.is_active == "true")
        result = await db.execute(stmt)
        plans =  result.scalars().all()
        
        # Format response
        return [
            {
                "id": plan.id,
                "name": plan.name,
                "slug": plan.slug,
                "price": plan.price,
                "features": plan.features or {"feature_list": []},
                "limits": plan.limits or {},
                "is_active": plan.is_active,
                "is_popular": plan.is_popular,
                "created_at": plan.created_at.isoformat() if plan.created_at else None,
                "updated_at": plan.updated_at.isoformat() if plan.updated_at else None
            }
            for plan in plans
        ]


# Singleton instance
checkout_service = None


def get_checkout_service() -> CheckoutService:
    """
    Dependency injection helper for FastAPI routes.
    Returns the global checkout service instance.
    """
    global checkout_service
    if checkout_service is None:
        checkout_service = CheckoutService(get_billing_service())
    return checkout_service
