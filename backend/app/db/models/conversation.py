"""
Conversation Models

Models for conversations and messages.
"""

from sqlalchemy import Column, String, Integer, Text, JSON, ForeignKey, Float, BigInteger, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin
import uuid
import enum


class MessageRole(str, enum.Enum):
    """Enumeration of message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base, TimestampMixin):
    """
    Conversation model representing a chat session between a user and a bot.
    """
    
    __tablename__ = "conversations"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the conversation"
    )
    
    # Foreign Keys
    bot_id = Column(
        String(36),
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the bot"
    )
    
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the organization (for tenant isolation)"
    )
    
    # Session Information
    session_id = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Session ID for tracking anonymous users"
    )
    
    visitor_id = Column(
        String(100),
        nullable=True,
        comment="Visitor identifier (can be anonymous)"
    )
    
    # Timing
    started_at = Column(
        String(100),
        nullable=False,
        comment="When the conversation started"
    )
    
    ended_at = Column(
        String(100),
        nullable=True,
        comment="When the conversation ended"
    )
    
    duration = Column(
        Integer,
        nullable=True,
        comment="Duration of conversation in seconds"
    )
    
    # Feedback
    rating = Column(
        Integer,
        nullable=True,
        comment="User rating (1-5 stars)"
    )
    
    feedback = Column(
        Text,
        nullable=True,
        comment="User feedback text"
    )
    
    feedback_category = Column(
        String(50),
        nullable=True,
        comment="Category of feedback (helpful, not_helpful, inaccurate, etc.)"
    )
    
    # Metadata
    meta_data = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Additional metadata (user_agent, ip, location, etc.)"
    )
    # Example structure:
    # {
    #     "user_agent": "Mozilla/5.0...",
    #     "ip_address": "192.168.1.1",
    #     "location": "US",
    #     "referrer": "https://example.com",
    #     "device_type": "desktop"
    # }
    
    # Statistics
    message_count = Column(
        Integer,
        default=0,
        comment="Total number of messages in this conversation"
    )
    
    avg_response_time = Column(
        Float,
        nullable=True,
        comment="Average response time in seconds"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    bot = relationship("Bot", back_populates="conversations")
    organization = relationship("Organization", back_populates="conversations")
    
    # Messages in this conversation
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.timestamp"
    )
    
    # Events for this conversation
    events = relationship(
        "Event",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, bot_id={self.bot_id}, message_count={self.message_count})>"
    
    def to_dict(self) -> dict:
        """Convert conversation to dictionary"""
        return {
            "id": self.id,
            "bot_id": self.bot_id,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration": self.duration,
            "rating": self.rating,
            "feedback": self.feedback,
            "message_count": self.message_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Message(Base):
    """
    Message model representing individual messages in a conversation.
    """
    
    __tablename__ = "messages"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the message"
    )
    
    # Foreign Keys
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the conversation"
    )
    
    # Message Content
    role = Column(
        SQLEnum(MessageRole),
        nullable=False,
        comment="Role of the message sender (user, assistant, system)"
    )
    
    content = Column(
        Text,
        nullable=False,
        comment="Message content"
    )
    
    timestamp = Column(
        String(100),
        nullable=False,
        index=True,
        comment="When the message was sent"
    )
    
    # Sources Used (for assistant messages)
    sources_used = Column(
        JSON,
        nullable=True,
        default=list,
        comment="List of knowledge source IDs used to generate this response"
    )
    
    # Source details for citation
    source_details = Column(
        JSON,
        nullable=True,
        default=list,
        comment="Detailed information about sources used"
    )
    # Example structure:
    # [
    #     {
    #         "source_id": "...",
    #         "chunk_id": "...",
    #         "content": "relevant text",
    #         "source_type": "document",
    #         "source_name": "file.pdf",
    #         "page": 5,
    #         "similarity_score": 0.85
    #     }
    # ]
    
    # Performance Metrics
    latency_ms = Column(
        Integer,
        nullable=True,
        comment="Response latency in milliseconds"
    )
    
    token_count = Column(
        Integer,
        nullable=True,
        comment="Number of tokens in the response"
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
    
    conversation = relationship("Conversation", back_populates="messages")
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"
    
    def to_dict(self) -> dict:
        """Convert message to dictionary"""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "sources_used": self.sources_used,
            "source_details": self.source_details,
            "latency_ms": self.latency_ms,
        }


