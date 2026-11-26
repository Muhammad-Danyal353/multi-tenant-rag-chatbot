"""
Audit Log Model

This module defines the SQLAlchemy model for audit logs.
"""

from sqlalchemy import Column, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime
import uuid


class AuditLog(Base):
    """
    Audit log model for tracking user actions and changes to resources.
    """
    
    __tablename__ = "audit_logs"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the audit log"
    )
    
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the organization"
    )
    
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed the action"
    )
    
    action = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Action performed (create, update, delete, etc.)"
    )
    
    resource_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of resource affected (bot, knowledge_base, etc.)"
    )
    
    resource_id = Column(
        String(36),
        nullable=True,
        index=True,
        comment="ID of the affected resource"
    )
    
    changes = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="JSON payload containing changes made (old_value, new_value)"
    )
    
    ip_address = Column(
        String(50),
        nullable=True,
        comment="IP address of the user"
    )
    
    meta_data = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Additional meta_data about the action"
    )
    
    timestamp = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Timestamp when the action occurred"
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, resource_type={self.resource_type})>"