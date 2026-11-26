"""
API Key Model

Represents API keys for bots.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin
import uuid
from datetime import datetime


class ApiKey(Base, TimestampMixin):
    """
    API Key model for bot authentication.
    
    Attributes:
        id: Unique identifier (UUID)
        bot_id: Reference to the bot
        name: Name/description for the API key
        key_hash: Hashed API key
        created_by: User who created the key
        expires_at: Optional expiration date
        last_used_at: When the key was last used
        is_active: Whether the key is active
    """
    
    __tablename__ = "api_keys"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the API key"
    )
    
    # Foreign Keys
    bot_id = Column(
        String(36),
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the bot"
    )
    
    # API Key Details
    name = Column(
        String(255),
        nullable=False,
        comment="Name/description for the API key"
    )
    
    key_hash = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Hashed API key"
    )
    
    created_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created the key"
    )
    
    expires_at = Column(
        DateTime,
        nullable=True,
        comment="Optional expiration date"
    )
    
    last_used_at = Column(
        DateTime,
        nullable=True,
        comment="When the key was last used"
    )
    
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the key is active"
    )
    
    # Relationships
    bot = relationship("Bot", back_populates="api_keys")
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, bot_id={self.bot_id}, name={self.name})>"
    
    def is_expired(self) -> bool:
        """Check if the API key has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if the API key is valid (active and not expired)"""
        return self.is_active and not self.is_expired()
