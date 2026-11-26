"""
User Model

Represents application users with authentication and profile information.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, SoftDeleteMixin
import uuid


class User(Base, TimestampMixin, SoftDeleteMixin):
    """
    User model for authentication and user management.
    
    Attributes:
        id: Unique identifier (UUID)
        email: User's email address (unique, used for login)
        hashed_password: Bcrypt hashed password
        full_name: User's full name
        is_active: Whether the account is active
        is_verified: Whether email is verified
        is_superadmin: Whether user has super admin privileges
        last_login: Timestamp of last login
        email_verification_token: Token for email verification
        reset_password_token: Token for password reset
    """
    
    __tablename__ = "users"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the user"
    )
    
    # Authentication Fields
    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="User's email address (unique, used for login)"
    )
    
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password"
    )
    
    # Profile Fields
    full_name = Column(
        String(255),
        nullable=False,
        comment="User's full name"
    )
    
    # Status Fields
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the account is active"
    )
    
    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether email is verified"
    )
    
    is_superadmin = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether user has super admin privileges"
    )
    
    # Activity Tracking
    last_login = Column(
        DateTime,
        nullable=True,
        comment="Timestamp of last login"
    )
    
    # Verification & Reset Tokens
    email_verification_token = Column(
        String(500),
        nullable=True,
        comment="Token for email verification"
    )
    
    reset_password_token = Column(
        String(500),
        nullable=True,
        comment="Token for password reset"
    )
    
    reset_password_token_expires = Column(
        DateTime,
        nullable=True,
        comment="Expiration time for password reset token"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    # User can belong to multiple organizations through memberships
    memberships = relationship(
        "Membership",
        back_populates="user",
        foreign_keys="Membership.user_id",
        cascade="all, delete-orphan"
    )
    
    # User's created bots
    created_bots = relationship(
        "Bot",
        back_populates="creator",
        foreign_keys="Bot.created_by"
    )
    
    # User's audit logs
    audit_logs = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Invitations sent by this user
    sent_invitations = relationship(
        "Membership",
        foreign_keys="Membership.invited_by",
        cascade="all, delete-orphan"
    )
    
    # Events for this user
    events = relationship(
        "Event",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, full_name={self.full_name})>"
    
    def to_dict(self) -> dict:
        """Convert user to dictionary (excluding sensitive fields)"""
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

