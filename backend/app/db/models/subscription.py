"""
Subscription Models

Models for subscription plans, subscriptions, and usage tracking.
"""

from sqlalchemy import Column, String, Integer, Float, JSON, ForeignKey, BigInteger, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin
import uuid
import enum


class PlanType(str, enum.Enum):
    """Enumeration of plan types"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    """Enumeration of subscription statuses"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    UNPAID = "unpaid"
    PENDING = "pending"


class Plan(Base, TimestampMixin):
    """
    Plan model representing subscription plans.
    
    Defines the features and limits for each plan tier.
    """
    
    __tablename__ = "plans"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the plan"
    )
    
    # Plan Information
    name = Column(
        String(100),
        nullable=False,
        comment="Plan name (e.g., Free, Pro, Enterprise)"
    )
    
    slug = Column(
        String(50),
        unique=True,
        nullable=False,
        comment="URL-friendly slug"
    )
    
    price = Column(
        Float,
        nullable=False,
        default=0.0,
        comment="Monthly price in USD"
    )
    
    # Features (JSON for flexibility)
    features = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="List of features included in this plan"
    )
    # Example structure:
    # {
    #     "feature_list": [
    #         "Unlimited bots",
    #         "Advanced analytics",
    #         "Priority support"
    #     ],
    #     "highlighted_features": [...]
    # }
    
    # Limits (JSON for flexibility)
    limits = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Usage limits for this plan"
    )
    # Example structure:
    # {
    #     "max_bots": 5,
    #     "max_messages_per_month": 1000,
    #     "max_storage_mb": 500,
    #     "max_knowledge_sources": 50,
    #     "max_api_calls_per_day": 10000
    # }
    
    # Status
    is_active = Column(
        String(10),
        default="true",
        comment="Whether this plan is available for new subscriptions"
    )
    
    is_popular = Column(
        String(10),
        default="false",
        comment="Whether to highlight this plan as popular"
    )
    
    # Payment Integration
    payment_provider = Column(
        String(50),
        default="lemonsqueezy",
        nullable=True,
        comment="Payment provider (lemonsqueezy, stripe, etc.)"
    )
    
    payment_price_id = Column(
        String(100),
        nullable=True,
        comment="Payment provider price/variant ID for this plan"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    subscriptions = relationship(
        "Subscription",
        back_populates="plan"
    )
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Plan(id={self.id}, name={self.name}, price=${self.price})>"


class Subscription(Base, TimestampMixin):
    """
    Subscription model representing organization subscriptions to plans.
    """
    
    __tablename__ = "subscriptions"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the subscription"
    )
    
    # Foreign Keys
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to the organization"
    )
    
    plan_id = Column(
        String(36),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Reference to the plan"
    )
    
    # Subscription Status
    status = Column(
        SQLEnum(SubscriptionStatus),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
        comment="Current subscription status"
    )
    
    # Billing Period
    current_period_start = Column(
        String(100),
        nullable=True,
        comment="Start of the current billing period"
    )
    
    current_period_end = Column(
        String(100),
        nullable=True,
        comment="End of the current billing period"
    )
    
    trial_end = Column(
        String(100),
        nullable=True,
        comment="End of trial period (if applicable)"
    )
    
    # Payment Integration
    payment_provider = Column(
        String(50),
        default="lemonsqueezy",
        nullable=True,
        comment="Payment provider (lemonsqueezy, stripe, etc.)"
    )
    
    lemonsqueezy_subscription_id = Column(
        String(100),
        unique=True,
        nullable=True,
        comment="Lemon Squeezy subscription ID"
    )
    
    lemonsqueezy_customer_id = Column(
        String(100),
        nullable=True,
        comment="Lemon Squeezy customer ID"
    )
    
    lemonsqueezy_order_id = Column(
        String(100),
        nullable=True,
        comment="Lemon Squeezy order ID"
    )
    
    # Legacy Stripe fields (for backward compatibility)
    stripe_subscription_id = Column(
        String(100),
        unique=True,
        nullable=True,
        comment="Stripe subscription ID (legacy)"
    )
    
    stripe_customer_id = Column(
        String(100),
        nullable=True,
        comment="Stripe customer ID (legacy)"
    )
    
    # Cancellation
    cancel_at_period_end = Column(
        String(10),
        default="false",
        comment="Whether to cancel at the end of the current period"
    )
    
    cancelled_at = Column(
        String(100),
        nullable=True,
        comment="When the subscription was cancelled"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    organization = relationship("Organization", back_populates="subscription")
    plan = relationship("Plan", back_populates="subscriptions")
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, org_id={self.organization_id}, status={self.status})>"


class UsageCounter(Base, TimestampMixin):
    """
    Usage counter model for tracking resource usage per organization.
    
    Tracks usage against plan limits.
    """
    
    __tablename__ = "usage_counters"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the usage counter"
    )
    
    # Foreign Keys
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the organization"
    )
    
    # Metric Information
    metric_type = Column(
        String(50),
        nullable=False,
        comment="Type of metric (e.g., messages, storage, api_calls)"
    )
    
    count = Column(
        BigInteger,
        default=0,
        nullable=False,
        comment="Current count"
    )
    
    # Period
    period_start = Column(
        String(100),
        nullable=False,
        comment="Start of the tracking period"
    )
    
    period_end = Column(
        String(100),
        nullable=False,
        comment="End of the tracking period"
    )
    
    reset_at = Column(
        String(100),
        nullable=True,
        comment="When the counter will reset"
    )
    
    # Metadata
    meta_data = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Additional metadata"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    organization = relationship("Organization", back_populates="usage_counters")
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<UsageCounter(org_id={self.organization_id}, metric={self.metric_type}, count={self.count})>"
    
    def increment(self, amount: int = 1):
        """Increment the usage counter"""
        self.count += amount
    
    def reset(self):
        """Reset the usage counter"""
        self.count = 0

