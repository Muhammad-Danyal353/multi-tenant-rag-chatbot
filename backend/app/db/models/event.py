"""
Event Model

Represents analytics events for tracking user interactions and system activities.
"""

from sqlalchemy import Column, String, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin
import uuid
import enum
from typing import Optional, Dict, Any


class EventType(str, enum.Enum):
    """Enumeration of event types for analytics tracking"""
    
    # User interaction events
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_ENDED = "conversation_ended"
    FEEDBACK_SUBMITTED = "feedback_submitted"
    
    # Knowledge base events
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    WEBSITE_SCRAPED = "website_scraped"
    TEXT_CONTENT_CREATED = "text_content_created"
    SOURCE_DELETED = "source_deleted"
    
    # Bot management events
    BOT_CREATED = "bot_created"
    BOT_UPDATED = "bot_updated"
    BOT_DELETED = "bot_deleted"
    API_KEY_GENERATED = "api_key_generated"
    
    # Widget events
    WIDGET_LOADED = "widget_loaded"
    WIDGET_OPENED = "widget_opened"
    WIDGET_CLOSED = "widget_closed"
    SUGGESTED_QUESTION_CLICKED = "suggested_question_clicked"
    
    # System events
    ERROR_OCCURRED = "error_occurred"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    QUOTA_EXCEEDED = "quota_exceeded"
    
    # Authentication events
    USER_LOGGED_IN = "user_logged_in"
    USER_LOGGED_OUT = "user_logged_out"
    USER_REGISTERED = "user_registered"
    PASSWORD_RESET = "password_reset"


class Event(Base, TimestampMixin):
    """
    Event model for tracking analytics events.
    """
    
    __tablename__ = "events"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the event"
    )
    
    # Foreign Keys
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this event"
    )
    
    bot_id = Column(
        String(36),
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Bot associated with this event (if applicable)"
    )
    
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who triggered this event (if applicable)"
    )
    
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Conversation associated with this event (if applicable)"
    )
    
    # Event Information
    event_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of event"
    )
    
    event_data = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Additional event data (JSON)"
    )
    
    # Session tracking
    session_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Session ID for tracking user sessions"
    )
    
    visitor_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Visitor ID for anonymous users"
    )
    
    # Client information
    client_info = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Client information (user agent, IP, etc.)"
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="events")
    bot = relationship("Bot", back_populates="events")
    user = relationship("User", back_populates="events")
    conversation = relationship("Conversation", back_populates="events")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_events_type_timestamp', event_type, 'created_at'),
        Index('idx_events_org_timestamp', organization_id, 'created_at'),
        Index('idx_events_bot_timestamp', bot_id, 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Event(id={self.id}, type={self.event_type})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "bot_id": self.bot_id,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "event_type": self.event_type,
            "event_data": self.event_data,
            "session_id": self.session_id,
            "visitor_id": self.visitor_id,
            "client_info": self.client_info,
            "timestamp": self.created_at.isoformat() if self.created_at else None
        }
