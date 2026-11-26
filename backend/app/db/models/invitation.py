"""
Invitation Model

Represents invitations to join organizations.
"""

from sqlalchemy import Column, String, Enum as SQLEnum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin
from app.db.models.organization import MemberRole
import uuid
from datetime import datetime, timedelta


class Invitation(Base, TimestampMixin):
    """
    Invitation model for inviting users to join organizations.
    """
    
    __tablename__ = "invitations"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the invitation"
    )
    
    # Foreign Keys
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the organization"
    )
    
    invited_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who sent the invitation"
    )
    
    # Invitation Details
    email = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Email address of the invitee"
    )
    
    role = Column(
        SQLEnum(MemberRole),
        default=MemberRole.MEMBER,
        nullable=False,
        comment="Role to assign to the invitee"
    )
    
    token = Column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
        comment="Invitation token"
    )
    
    expires_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(days=7),
        comment="Expiration date for the invitation"
    )
    
    accepted_at = Column(
        DateTime,
        nullable=True,
        comment="When the invitation was accepted"
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="invitations")
    inviter = relationship("User", foreign_keys=[invited_by])
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Invitation(id={self.id}, email={self.email}, org_id={self.organization_id})>"
    
    def is_expired(self) -> bool:
        """Check if the invitation has expired"""
        return datetime.utcnow() > self.expires_at
    
    def is_accepted(self) -> bool:
        """Check if the invitation has been accepted"""
        return self.accepted_at is not None
    
    def to_dict(self) -> dict:
        """Convert invitation to dictionary"""
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "email": self.email,
            "role": self.role.value,
            "invited_by": self.invited_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "is_expired": self.is_expired(),
            "is_accepted": self.is_accepted()
        }
