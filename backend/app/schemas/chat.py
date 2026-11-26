"""
Chat Schemas

Pydantic schemas for chat-related API requests and responses.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    """Message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant"


class SendMessageRequest(BaseModel):
    """Request schema for sending a message."""
    
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message content"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Existing conversation ID (optional)"
    )
    visitor_id: Optional[str] = Field(
        None,
        description="Visitor ID for anonymous users"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata"
    )
    
    @validator("message")
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class SendMessageResponse(BaseModel):
    """Response schema for sending a message."""
    
    response: str = Field(..., description="AI response content")
    conversation_id: str = Field(..., description="Conversation ID")
    message_id: str = Field(..., description="Message ID")
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Source attribution information"
    )
    latency_ms: float = Field(..., description="Response latency in milliseconds")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Response metadata"
    )


class SourceAttribution(BaseModel):
    """Source attribution schema."""
    
    content: str = Field(..., description="Source content snippet")
    source_type: str = Field(..., description="Type of source (document, web, text)")
    source_id: Optional[str] = Field(None, description="Source ID")
    source_name: Optional[str] = Field(None, description="Source name")
    score: float = Field(..., description="Relevance score")
    
    # Document-specific fields
    page: Optional[int] = Field(None, description="Page number (for documents)")
    section: Optional[str] = Field(None, description="Section (for documents)")
    
    # Web-specific fields
    url: Optional[str] = Field(None, description="URL (for web sources)")
    domain: Optional[str] = Field(None, description="Domain (for web sources)")
    
    # Text-specific fields
    category: Optional[str] = Field(None, description="Category (for text sources)")
    tags: Optional[List[str]] = Field(None, description="Tags (for text sources)")


class MessageResponse(BaseModel):
    """Message response schema."""
    
    id: str = Field(..., description="Message ID")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    sources_used: List[str] = Field(
        default_factory=list,
        description="List of source IDs used"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Message metadata"
    )


class ConversationResponse(BaseModel):
    """Conversation response schema."""
    
    id: str = Field(..., description="Conversation ID")
    bot_id: str = Field(..., description="Bot ID")
    session_id: str = Field(..., description="Session ID")
    visitor_id: Optional[str] = Field(None, description="Visitor ID")
    started_at: datetime = Field(..., description="Conversation start time")
    ended_at: Optional[datetime] = Field(None, description="Conversation end time")
    last_message_at: Optional[datetime] = Field(None, description="Last message time")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Conversation rating")
    feedback: Optional[str] = Field(None, description="Conversation feedback")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Conversation metadata"
    )
    messages: List[MessageResponse] = Field(
        default_factory=list,
        description="Conversation messages"
    )


class ConversationSummary(BaseModel):
    """Conversation summary schema for listing."""
    
    id: str = Field(..., description="Conversation ID")
    bot_id: str = Field(..., description="Bot ID")
    session_id: str = Field(..., description="Session ID")
    visitor_id: Optional[str] = Field(None, description="Visitor ID")
    started_at: datetime = Field(..., description="Conversation start time")
    ended_at: Optional[datetime] = Field(None, description="Conversation end time")
    last_message_at: Optional[datetime] = Field(None, description="Last message time")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Conversation rating")
    feedback: Optional[str] = Field(None, description="Conversation feedback")
    message_count: int = Field(..., description="Number of messages in conversation")


class ListConversationsResponse(BaseModel):
    """Response schema for listing conversations."""
    
    conversations: List[ConversationSummary] = Field(
        ...,
        description="List of conversations"
    )
    total: int = Field(..., description="Total number of conversations")
    limit: int = Field(..., description="Limit applied")
    offset: int = Field(..., description="Offset applied")


class SubmitFeedbackRequest(BaseModel):
    """Request schema for submitting feedback."""
    
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Rating from 1 to 5"
    )
    feedback: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional text feedback"
    )


class SubmitFeedbackResponse(BaseModel):
    """Response schema for submitting feedback."""
    
    success: bool = Field(..., description="Success status")
    message: str = Field(..., description="Response message")
    conversation_id: str = Field(..., description="Conversation ID")
    rating: int = Field(..., description="Submitted rating")


class ChatStatsResponse(BaseModel):
    """Response schema for chat statistics."""
    
    total_conversations: int = Field(..., description="Total conversations")
    total_messages: int = Field(..., description="Total messages")
    average_rating: Optional[float] = Field(None, description="Average conversation rating")
    average_response_time: Optional[float] = Field(None, description="Average response time in ms")
    top_queries: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Most common queries"
    )
    satisfaction_score: Optional[float] = Field(None, description="Overall satisfaction score")


class StreamMessageRequest(BaseModel):
    """Request schema for streaming messages."""
    
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message content"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Existing conversation ID (optional)"
    )
    visitor_id: Optional[str] = Field(
        None,
        description="Visitor ID for anonymous users"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata"
    )


class StreamMessageChunk(BaseModel):
    """Streaming message chunk schema."""
    
    type: str = Field(..., description="Chunk type (content, metadata, error)")
    data: Any = Field(..., description="Chunk data")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    message_id: Optional[str] = Field(None, description="Message ID")


class SearchRequest(BaseModel):
    """Request schema for knowledge base search."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query"
    )
    top_k: Optional[int] = Field(
        None,
        ge=1,
        le=20,
        description="Number of results to return"
    )
    source_types: Optional[List[str]] = Field(
        None,
        description="Filter by source types"
    )
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional filters"
    )


class SearchResult(BaseModel):
    """Search result schema."""
    
    id: str = Field(..., description="Result ID")
    content: str = Field(..., description="Content snippet")
    score: float = Field(..., description="Relevance score")
    metadata: Dict[str, Any] = Field(..., description="Result metadata")
    source_attribution: SourceAttribution = Field(..., description="Source information")


class SearchResponse(BaseModel):
    """Response schema for knowledge base search."""
    
    results: List[SearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total number of results")
    query: str = Field(..., description="Original query")
    latency_ms: float = Field(..., description="Search latency in milliseconds")
