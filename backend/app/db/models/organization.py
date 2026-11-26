"""
Organization Model

Represents organizations (tenants) in the multi-tenant system.
"""

from sqlalchemy import Column, String, Boolean, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, SoftDeleteMixin
import uuid
import enum


class MemberRole(str, enum.Enum):
    """Enumeration of possible member roles in an organization"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class SubscriptionPlan(str, enum.Enum):
    """Enumeration of subscription plans"""
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


class Organization(Base, TimestampMixin, SoftDeleteMixin):
    """
    Organization model for multi-tenancy.
    
    Each organization represents a separate tenant with isolated data.
    """
    
    __tablename__ = "organizations"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the organization"
    )
    
    # Basic Information
    name = Column(
        String(255),
        nullable=False,
        comment="Organization name"
    )
    
    slug = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="URL-friendly slug for the organization"
    )
    
    # Subscription Information
    subscription_plan = Column(
        SQLEnum(SubscriptionPlan),
        default=SubscriptionPlan.FREE,
        nullable=False,
        comment="Current subscription plan"
    )
    
    subscription_status = Column(
        SQLEnum(SubscriptionStatus),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
        comment="Current subscription status"
    )
    
    # Usage Limits (JSON field for flexibility)
    usage_limits = Column(
        JSON,
        nullable=True,
        comment="Usage limits based on subscription plan"
    )
    
    # Settings
    settings = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Organization-level settings (branding, defaults, etc.)"
    )
    
    # Status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the organization is active"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    # Members of this organization
    memberships = relationship(
        "Membership",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    
    # Bots belonging to this organization
    bots = relationship(
        "Bot",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    
    # Conversations in this organization
    conversations = relationship(
        "Conversation",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    
    # Events in this organization
    events = relationship(
        "Event",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    
    # Subscription
    subscription = relationship(
        "Subscription",
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Audit logs
    audit_logs = relationship(
        "AuditLog",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    
    # Usage counters
    usage_counters = relationship(
        "UsageCounter",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    
    # Invitations
    invitations = relationship(
        "Invitation",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name}, plan={self.subscription_plan})>"
    
    def to_dict(self) -> dict:
        """Convert organization to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "subscription_plan": self.subscription_plan.value,
            "subscription_status": self.subscription_status.value,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Membership(Base, TimestampMixin):
    """
    Membership model representing user-organization relationships.
    
    This is the junction table between users and organizations with role information.
    """
    
    __tablename__ = "memberships"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the membership"
    )
    
    # Foreign Keys
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the user"
    )
    
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the organization"
    )
    
    # Role
    role = Column(
        SQLEnum(MemberRole),
        default=MemberRole.MEMBER,
        nullable=False,
        comment="User's role in the organization"
    )
    
    # Invitation Tracking
    invited_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who invited this member"
    )
    
    invitation_accepted_at = Column(
        String(100),
        nullable=True,
        comment="When the invitation was accepted"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    user = relationship("User", back_populates="memberships", foreign_keys=[user_id])
    organization = relationship("Organization", back_populates="memberships")
    inviter = relationship("User", foreign_keys=[invited_by], overlaps="sent_invitations")
    
    # ========================================================================
    # CONSTRAINTS
    # ========================================================================
    
    __table_args__ = (
        # Ensure a user can only have one membership per organization
        # UniqueConstraint('user_id', 'organization_id', name='unique_user_org'),
    )
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Membership(user_id={self.user_id}, org_id={self.organization_id}, role={self.role})>"

