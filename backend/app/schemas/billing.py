"""
Billing Schemas

This module defines Pydantic models for billing and subscription management.
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum


class PlanType(str, Enum):
    """Plan type enumeration"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    UNPAID = "unpaid"
    PENDING = "pending"


class CheckoutSessionCreate(BaseModel):
    """
    Schema for creating a checkout session.
    """
    plan_id: PlanType
    organization_id: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CheckoutSessionResponse(BaseModel):
    """
    Schema for checkout session response.
    """
    checkout_id: str
    checkout_url: str
    expires_at: Optional[str] = None


class SubscriptionBase(BaseModel):
    """
    Base schema for subscription data.
    """
    organization_id: str
    plan_id: PlanType
    status: SubscriptionStatus
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    trial_end: Optional[str] = None
    cancel_at_period_end: Optional[bool] = False


class SubscriptionCreate(SubscriptionBase):
    """
    Schema for creating a subscription.
    """
    pass


class SubscriptionUpdate(BaseModel):
    """
    Schema for updating a subscription.
    """
    plan_id: Optional[PlanType] = None
    status: Optional[SubscriptionStatus] = None
    cancel_at_period_end: Optional[bool] = None


class SubscriptionResponse(SubscriptionBase):
    """
    Schema for subscription response.
    """
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    """
    Schema for list of subscriptions.
    """
    items: List[SubscriptionResponse]
    total: int


class PlanFeatures(BaseModel):
    """
    Schema for plan features.
    """
    feature_list: List[str] = []
    highlighted_features: Optional[List[str]] = None


class PlanLimits(BaseModel):
    """
    Schema for plan limits.
    """
    max_bots: int
    max_messages_per_month: int
    max_storage_mb: int
    max_knowledge_sources: int
    max_api_calls_per_day: Optional[int] = None


class PlanBase(BaseModel):
    """
    Base schema for plan data.
    """
    name: str
    slug: str
    price: float
    features: PlanFeatures
    limits: PlanLimits
    is_active: str = "true"
    is_popular: str = "false"


class PlanCreate(PlanBase):
    """
    Schema for creating a plan.
    """
    pass


class PlanUpdate(BaseModel):
    """
    Schema for updating a plan.
    """
    name: Optional[str] = None
    price: Optional[float] = None
    features: Optional[PlanFeatures] = None
    limits: Optional[PlanLimits] = None
    is_active: Optional[str] = None
    is_popular: Optional[str] = None


class PlanResponse(PlanBase):
    """
    Schema for plan response.
    """
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class PlanListResponse(BaseModel):
    """
    Schema for list of plans.
    """
    items: List[PlanResponse]
    total: int


class UsageMetric(BaseModel):
    """
    Schema for usage metric.
    """
    used: int
    limit: int


class UsageResponse(BaseModel):
    """
    Schema for usage response.
    """
    plan: str
    messages: UsageMetric
    storage: UsageMetric
    bots: UsageMetric
    knowledge_sources: Optional[UsageMetric] = None
    api_calls: Optional[UsageMetric] = None


class WebhookResponse(BaseModel):
    """
    Schema for webhook response.
    """
    status: str
    event: str
