"""
Billing API Routes

This module defines the FastAPI routes for billing and subscription management.
Includes webhook endpoints for Lemon Squeezy integration.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, get_async_db
from app.core.dependencies import get_current_user, require_permission
from app.services.billing_service import get_billing_service, BillingService
from app.services.checkout_service import get_checkout_service, CheckoutService
from app.services.usage_service import get_usage_service, UsageService
from app.schemas.auth import UserResponse
from app.schemas.billing import (
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    SubscriptionResponse,
    SubscriptionListResponse,
    WebhookResponse,
    PlanResponse,
    PlanListResponse,
    UsageResponse
)
from app.schemas.base import ApiResponse
from app.utils.response import create_response
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/checkout", 
    response_model=ApiResponse[CheckoutSessionResponse],
    summary="Create a checkout session for subscription"
)
async def create_checkout_session(
    data: CheckoutSessionCreate,
    current_user: UserResponse = Depends(get_current_user),
    checkout_service: CheckoutService = Depends(get_checkout_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Create a checkout session for a subscription plan.
    
    This endpoint generates a Lemon Squeezy checkout URL for the specified plan.
    The user will be redirected to this URL to complete the payment process.
    """
    # Check permissions
    require_permission(current_user, "billing:manage")
    
    # Create checkout session using the checkout service
    checkout = await checkout_service.create_checkout_session(
        data=data,
        user_id=current_user.id,
        user_email=current_user.email,
        db=db
    )
    
    return create_response(
        data=checkout,
        message="Checkout session created successfully"
    )


@router.get(
    "/subscriptions/{organization_id}",
    response_model=ApiResponse[SubscriptionResponse],
    summary="Get subscription details for an organization"
)
async def get_subscription(
    organization_id: str,
    current_user: UserResponse = Depends(get_current_user),
    checkout_service: CheckoutService = Depends(get_checkout_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get subscription details for the specified organization.
    
    Returns the current subscription plan, status, and billing period.
    """
    # Check permissions
    require_permission(current_user, "billing:view", organization_id=organization_id)
    
    # Query the subscription using the checkout service
    subscription = await checkout_service.get_subscription(organization_id, db)
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No subscription found for organization {organization_id}"
        )
    
    return create_response(
        data=subscription,
        message="Subscription details retrieved successfully"
    )


@router.post(
    "/cancel-subscription/{organization_id}",
    response_model=ApiResponse[SubscriptionResponse],
    summary="Cancel a subscription"
)
async def cancel_subscription(
    organization_id: str,
    current_user: UserResponse = Depends(get_current_user),
    checkout_service: CheckoutService = Depends(get_checkout_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Cancel the subscription for the specified organization.
    
    The subscription will remain active until the end of the current billing period.
    """
    # Check permissions
    require_permission(current_user, "billing:manage", organization_id=organization_id)
    
    # Cancel subscription using the checkout service
    subscription = await checkout_service.cancel_subscription(organization_id, db)
    
    return create_response(
        data=subscription,
        message="Subscription cancelled successfully"
    )


@router.get(
    "/plans",
    response_model=ApiResponse[PlanListResponse],
    summary="List available subscription plans"
)
async def list_plans(
    checkout_service: CheckoutService = Depends(get_checkout_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List all available subscription plans.
    
    Returns plan details including features, limits, and pricing.
    """
    # Query plans using the checkout service
    plans = await checkout_service.list_plans(db)
    
    return create_response(
        data={
            "items": plans,
            "total": len(plans)
        },
        message="Subscription plans retrieved successfully"
    )


@router.get(
    "/usage/{organization_id}",
    response_model=ApiResponse[UsageResponse],
    summary="Get current usage metrics"
)
async def get_usage(
    organization_id: str,
    current_user: UserResponse = Depends(get_current_user),
    usage_service: UsageService = Depends(get_usage_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current usage metrics for the specified organization.
    
    Returns usage counts against plan limits.
    """
    # Check permissions
    require_permission(current_user, "billing:view", organization_id=organization_id)
    
    # Query usage using the usage service
    usage = await usage_service.get_organization_usage(organization_id, db)
    
    return create_response(
        data=usage,
        message="Usage metrics retrieved successfully"
    )


@router.post(
    "/webhooks/lemonsqueezy",
    response_model=ApiResponse[WebhookResponse],
    summary="Webhook endpoint for Lemon Squeezy events"
)
async def lemon_squeezy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    billing_service: BillingService = Depends(get_billing_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Webhook endpoint for Lemon Squeezy events.
    
    This endpoint receives webhook notifications from Lemon Squeezy
    for events like subscription creation, updates, cancellations, etc.
    """
    # Get raw request body
    body = await request.body()
    
    # Get signature header
    signature = request.headers.get("x-signature")
    if not signature:
        logger.warning("Missing signature header in webhook request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing signature header"
        )
    
    # Verify signature
    if not billing_service.verify_webhook_signature(body, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    
    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Error parsing webhook payload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    # Extract event type
    event_type = payload.get("meta", {}).get("event_name")
    if not event_type:
        logger.warning("Missing event_name in webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event_name"
        )
    
    # Process webhook event in background task to respond quickly
    background_tasks.add_task(
        billing_service.process_webhook_event,
        event_type=event_type,
        payload=payload,
        db=db
    )
    
    # Return success response immediately
    return {"status": "success", "event": event_type}
