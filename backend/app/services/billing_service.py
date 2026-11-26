"""
Billing Service for Lemon Squeezy Integration

This module handles all interactions with the Lemon Squeezy API for subscription
management, checkout creation, and webhook event processing.
"""

import hmac
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import httpx
from fastapi import HTTPException, Request, status

from app.config import settings
from app.db.models.subscription import Subscription
from app.db.models.organization import Organization
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


class BillingService:
    """
    Service for interacting with Lemon Squeezy API for billing and subscription management.
    """

    def __init__(self):
        """Initialize the billing service with API configuration."""
        self.api_key = settings.LEMONSQUEEZY_API_KEY
        self.store_id = settings.LEMONSQUEEZY_STORE_ID
        self.base_url = settings.LEMONSQUEEZY_BASE_URL
        self.webhook_secret = settings.LEMONSQUEEZY_WEBHOOK_SECRET
        
        # Plan variant IDs
        self.free_variant_id = settings.LEMONSQUEEZY_FREE_VARIANT_ID
        self.pro_variant_id = settings.LEMONSQUEEZY_PRO_VARIANT_ID
        self.enterprise_variant_id = settings.LEMONSQUEEZY_ENTERPRISE_VARIANT_ID
        
        # Checkout URLs
        self.success_url = settings.LEMONSQUEEZY_CHECKOUT_SUCCESS_URL
        self.cancel_url = settings.LEMONSQUEEZY_CHECKOUT_CANCEL_URL
        
        # Plan mapping
        self.variant_to_plan = {
            self.free_variant_id: "free",
            self.pro_variant_id: "pro",
            self.enterprise_variant_id: "enterprise"
        }
        
        self.plan_to_variant = {
            "free": self.free_variant_id,
            "pro": self.pro_variant_id,
            "enterprise": self.enterprise_variant_id
        }

    def _get_headers(self) -> Dict[str, str]:
        """
        Get the headers required for Lemon Squeezy API requests.
        
        Returns:
            Dict[str, str]: Headers for API requests
        """
        if not self.api_key:
            raise ValueError("Lemon Squeezy API key is not configured")
            
        return {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    async def create_checkout(self, variant_id: str, user_email: str, custom_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a checkout session for a specific product variant.
        
        Args:
            variant_id: The Lemon Squeezy variant ID
            user_email: The user's email address
            custom_data: Custom data to include with the checkout (organization_id, etc.)
            
        Returns:
            Dict[str, Any]: The checkout data including the URL
        """
        if not self.api_key or not self.store_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Billing service is not properly configured"
            )
        
        checkout_data = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "custom_price": None,  # Use the variant's configured price
                    "product_options": {
                        "name": "enabled",
                        "description": "enabled",
                        "media": "enabled",
                        "redirect_url": self.success_url,
                        "receipt_button_text": "Return to Dashboard",
                        "receipt_link_url": self.success_url,
                        "receipt_thank_you_note": "Thank you for your subscription!"
                    },
                    "checkout_data": {
                        "email": user_email,
                        "custom_data": custom_data
                    },
                    "preview": False,  # Set to True for testing
                    "test_mode": settings.ENVIRONMENT != "production"
                },
                "relationships": {
                    "store": {
                        "data": {
                            "type": "stores",
                            "id": self.store_id
                        }
                    },
                    "variant": {
                        "data": {
                            "type": "variants",
                            "id": variant_id
                        }
                    }
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/checkouts",
                    headers=self._get_headers(),
                    json=checkout_data
                )
                
                if response.status_code != 201:
                    logger.error(f"Failed to create checkout: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create checkout"
                    )
                
                checkout_response = response.json()
                return {
                    "checkout_id": checkout_response["data"]["id"],
                    "checkout_url": checkout_response["data"]["attributes"]["url"],
                    "expires_at": checkout_response["data"]["attributes"]["expires_at"]
                }
        
        except httpx.RequestError as e:
            logger.error(f"Error creating checkout: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Billing service is currently unavailable"
            )
    
    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Get subscription details from Lemon Squeezy.
        
        Args:
            subscription_id: The Lemon Squeezy subscription ID
            
        Returns:
            Dict[str, Any]: The subscription data
        """
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Billing service is not properly configured"
            )
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/subscriptions/{subscription_id}",
                    headers=self._get_headers()
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to get subscription: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to get subscription details"
                    )
                
                return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"Error getting subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Billing service is currently unavailable"
            )
    
    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel a subscription in Lemon Squeezy.
        
        Args:
            subscription_id: The Lemon Squeezy subscription ID
            
        Returns:
            Dict[str, Any]: The updated subscription data
        """
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Billing service is not properly configured"
            )
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/subscriptions/{subscription_id}",
                    headers=self._get_headers()
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to cancel subscription: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to cancel subscription"
                    )
                
                return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Billing service is currently unavailable"
            )
    
    async def update_subscription_variant(self, subscription_id: str, variant_id: str) -> Dict[str, Any]:
        """
        Update a subscription's variant (plan change).
        
        Args:
            subscription_id: The Lemon Squeezy subscription ID
            variant_id: The new variant ID
            
        Returns:
            Dict[str, Any]: The updated subscription data
        """
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Billing service is not properly configured"
            )
        
        update_data = {
            "data": {
                "type": "subscriptions",
                "id": subscription_id,
                "attributes": {
                    "product_id": variant_id
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    f"{self.base_url}/subscriptions/{subscription_id}",
                    headers=self._get_headers(),
                    json=update_data
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to update subscription: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update subscription"
                    )
                
                return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"Error updating subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Billing service is currently unavailable"
            )
    
    def verify_webhook_signature(self, request_body: bytes, signature_header: str) -> bool:
        """
        Verify the webhook signature from Lemon Squeezy.
        
        Args:
            request_body: The raw request body
            signature_header: The signature header from Lemon Squeezy
            
        Returns:
            bool: True if the signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret is not configured, skipping signature verification")
            return True
        
        try:
            # Compute HMAC using the webhook secret
            computed_hmac = hmac.new(
                key=self.webhook_secret.encode(),
                msg=request_body,
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # Compare with the provided signature
            return hmac.compare_digest(computed_hmac, signature_header)
        
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    async def process_webhook_event(self, event_type: str, payload: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
        """
        Process a webhook event from Lemon Squeezy.
        
        Args:
            event_type: The type of event (subscription_created, subscription_updated, etc.)
            payload: The webhook payload
            db: Database session
            
        Returns:
            Dict[str, Any]: The processed event result
        """
        logger.info(f"Processing webhook event: {event_type}")
        
        # Extract common data from payload
        meta = payload.get("meta", {})
        custom_data = meta.get("custom_data", {})
        organization_id = custom_data.get("organization_id")
        
        if not organization_id:
            logger.warning(f"No organization_id in webhook payload: {payload}")
            return {"success": False, "reason": "No organization_id found"}
        
        # Process based on event type
        if event_type == "subscription_created":
            return await self._handle_subscription_created(payload, organization_id, db)
        
        elif event_type == "subscription_updated":
            return await self._handle_subscription_updated(payload, organization_id, db)
        
        elif event_type == "subscription_cancelled":
            return await self._handle_subscription_cancelled(payload, organization_id, db)
        
        elif event_type == "subscription_resumed":
            return await self._handle_subscription_resumed(payload, organization_id, db)
        
        elif event_type == "subscription_expired":
            return await self._handle_subscription_expired(payload, organization_id, db)
        
        elif event_type == "order_created":
            return await self._handle_order_created(payload, organization_id, db)
        
        elif event_type == "order_refunded":
            return await self._handle_order_refunded(payload, organization_id, db)
        
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            return {"success": True, "action": "ignored"}
    
    async def _handle_subscription_created(
        self, payload: Dict[str, Any], organization_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle subscription_created webhook event."""
        try:
            data = payload.get("data", {})
            attributes = data.get("attributes", {})
            
            # Extract subscription details
            subscription_id = data.get("id")
            status = attributes.get("status")
            variant_id = attributes.get("variant_id")
            
            # Get plan from variant ID
            plan = self.variant_to_plan.get(variant_id, "free")
            
            # Update organization and subscription in database
            stmt = select(Organization).where(Organization.id == organization_id)
            result = await db.execute(stmt)
            organization = result.scalar_one_or_none()
            
            if not organization:
                logger.error(f"Organization not found: {organization_id}")
                return {"success": False, "reason": "Organization not found"}
            
            # Create or update subscription
            stmt = select(Subscription).where(Subscription.organization_id == organization_id)
            result = await db.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if subscription:
                # Update existing subscription
                subscription.plan_id = plan
                subscription.status = status
                subscription.lemonsqueezy_subscription_id = subscription_id
                subscription.current_period_start = datetime.fromisoformat(attributes.get("renews_at", ""))
                subscription.current_period_end = datetime.fromisoformat(attributes.get("ends_at", ""))
                subscription.updated_at = datetime.utcnow()
            else:
                # Create new subscription
                subscription = Subscription(
                    organization_id=organization_id,
                    plan_id=plan,
                    status=status,
                    lemonsqueezy_subscription_id=subscription_id,
                    current_period_start=datetime.fromisoformat(attributes.get("renews_at", "")),
                    current_period_end=datetime.fromisoformat(attributes.get("ends_at", "")),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(subscription)
            
            # Update organization plan
            organization.subscription_plan = plan
            organization.subscription_status = status
            
            await db.commit()
            
            return {
                "success": True,
                "action": "subscription_created",
                "organization_id": organization_id,
                "plan": plan
            }
        
        except Exception as e:
            await db.rollback()
            logger.error(f"Error handling subscription_created: {str(e)}")
            return {"success": False, "reason": str(e)}
    
    async def _handle_subscription_updated(
        self, payload: Dict[str, Any], organization_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle subscription_updated webhook event."""
        try:
            data = payload.get("data", {})
            attributes = data.get("attributes", {})
            
            # Extract subscription details
            subscription_id = data.get("id")
            status = attributes.get("status")
            variant_id = attributes.get("variant_id")
            
            # Get plan from variant ID
            plan = self.variant_to_plan.get(variant_id, "free")
            
            # Update subscription in database
            stmt = select(Subscription).where(
                Subscription.lemonsqueezy_subscription_id == subscription_id
            )
            result = await db.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return {"success": False, "reason": "Subscription not found"}
            
            # Update subscription
            subscription.plan_id = plan
            subscription.status = status
            subscription.current_period_start = datetime.fromisoformat(attributes.get("renews_at", ""))
            subscription.current_period_end = datetime.fromisoformat(attributes.get("ends_at", ""))
            subscription.updated_at = datetime.utcnow()
            
            # Update organization
            stmt = select(Organization).where(Organization.id == organization_id)
            result = await db.execute(stmt)
            organization = result.scalar_one_or_none()
            
            if organization:
                organization.subscription_plan = plan
                organization.subscription_status = status
            
            await db.commit()
            
            return {
                "success": True,
                "action": "subscription_updated",
                "organization_id": organization_id,
                "plan": plan
            }
        
        except Exception as e:
            await db.rollback()
            logger.error(f"Error handling subscription_updated: {str(e)}")
            return {"success": False, "reason": str(e)}
    
    async def _handle_subscription_cancelled(
        self, payload: Dict[str, Any], organization_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle subscription_cancelled webhook event."""
        try:
            data = payload.get("data", {})
            attributes = data.get("attributes", {})
            
            # Extract subscription details
            subscription_id = data.get("id")
            status = attributes.get("status")
            
            # Update subscription in database
            stmt = select(Subscription).where(
                Subscription.lemonsqueezy_subscription_id == subscription_id
            )
            result = await db.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return {"success": False, "reason": "Subscription not found"}
            
            # Update subscription
            subscription.status = status
            subscription.updated_at = datetime.utcnow()
            
            # Update organization
            stmt = select(Organization).where(Organization.id == organization_id)
            result = await db.execute(stmt)
            organization = result.scalar_one_or_none()
            
            if organization:
                organization.subscription_status = status
            
            await db.commit()
            
            return {
                "success": True,
                "action": "subscription_cancelled",
                "organization_id": organization_id
            }
        
        except Exception as e:
            await db.rollback()
            logger.error(f"Error handling subscription_cancelled: {str(e)}")
            return {"success": False, "reason": str(e)}
    
    async def _handle_subscription_resumed(
        self, payload: Dict[str, Any], organization_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle subscription_resumed webhook event."""
        try:
            data = payload.get("data", {})
            attributes = data.get("attributes", {})
            
            # Extract subscription details
            subscription_id = data.get("id")
            status = attributes.get("status")
            
            # Update subscription in database
            stmt = select(Subscription).where(
                Subscription.lemonsqueezy_subscription_id == subscription_id
            )
            result = await db.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return {"success": False, "reason": "Subscription not found"}
            
            # Update subscription
            subscription.status = status
            subscription.updated_at = datetime.utcnow()
            
            # Update organization
            stmt = select(Organization).where(Organization.id == organization_id)
            result = await db.execute(stmt)
            organization = result.scalar_one_or_none()
            
            if organization:
                organization.subscription_status = status
            
            await db.commit()
            
            return {
                "success": True,
                "action": "subscription_resumed",
                "organization_id": organization_id
            }
        
        except Exception as e:
            await db.rollback()
            logger.error(f"Error handling subscription_resumed: {str(e)}")
            return {"success": False, "reason": str(e)}
    
    async def _handle_subscription_expired(
        self, payload: Dict[str, Any], organization_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle subscription_expired webhook event."""
        try:
            data = payload.get("data", {})
            subscription_id = data.get("id")
            
            # Update subscription in database
            stmt = select(Subscription).where(
                Subscription.lemonsqueezy_subscription_id == subscription_id
            )
            result = await db.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return {"success": False, "reason": "Subscription not found"}
            
            # Update subscription
            subscription.status = "expired"
            subscription.updated_at = datetime.utcnow()
            
            # Update organization to free plan
            stmt = select(Organization).where(Organization.id == organization_id)
            result = await db.execute(stmt)
            organization = result.scalar_one_or_none()
            
            if organization:
                organization.subscription_plan = "free"
                organization.subscription_status = "expired"
            
            await db.commit()
            
            return {
                "success": True,
                "action": "subscription_expired",
                "organization_id": organization_id
            }
        
        except Exception as e:
            await db.rollback()
            logger.error(f"Error handling subscription_expired: {str(e)}")
            return {"success": False, "reason": str(e)}
    
    async def _handle_order_created(
        self, payload: Dict[str, Any], organization_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle order_created webhook event."""
        # For one-time purchases or initial subscription orders
        logger.info(f"Order created for organization {organization_id}")
        return {"success": True, "action": "order_created"}
    
    async def _handle_order_refunded(
        self, payload: Dict[str, Any], organization_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle order_refunded webhook event."""
        try:
            # Handle refund logic
            logger.info(f"Order refunded for organization {organization_id}")
            
            # Update organization to free plan
            stmt = select(Organization).where(Organization.id == organization_id)
            result = await db.execute(stmt)
            organization = result.scalar_one_or_none()
            
            if organization:
                organization.subscription_plan = "free"
                organization.subscription_status = "refunded"
                await db.commit()
            
            return {"success": True, "action": "order_refunded"}
        
        except Exception as e:
            await db.rollback()
            logger.error(f"Error handling order_refunded: {str(e)}")
            return {"success": False, "reason": str(e)}


# Singleton instance
billing_service = BillingService()


def get_billing_service() -> BillingService:
    """
    Dependency injection helper for FastAPI routes.
    Returns the global billing service instance.
    """
    return billing_service
