"""
Conversation Schemas

This module defines Pydantic models for conversation data.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    """Message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageSource(BaseModel):
    """Source reference in a message."""
    content: str
    source_type: str
    source_name: str
    page: Optional[int] = None
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageBase(BaseModel):
    """Base schema for message data."""
    role: MessageRole
    content: str
    sources_used: Optional[List[MessageSource]] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageCreate(MessageBase):
    """Schema for creating a message."""
    pass


class MessageUpdate(BaseModel):
    """Schema for updating a message."""
    content: Optional[str] = None
    sources_used: Optional[List[MessageSource]] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageResponse(MessageBase):
    """Schema for message response."""
    id: str
    conversation_id: str
    timestamp: datetime
    latency_ms: Optional[float] = None
    token_count: Optional[int] = None
    
    class Config:
        from_attributes = True


class ConversationBase(BaseModel):
    """Base schema for conversation data."""
    bot_id: str
    session_id: Optional[str] = None
    visitor_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationCreate(ConversationBase):
    """Schema for creating a conversation."""
    pass


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""
    ended_at: Optional[datetime] = None
    duration: Optional[float] = None
    rating: Optional[int] = None
    feedback: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationResponse(ConversationBase):
    """Schema for conversation response."""
    id: str
    organization_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration: Optional[float] = None
    rating: Optional[int] = None
    feedback: Optional[str] = None
    
    class Config:
        from_attributes = True


class ConversationDetailResponse(ConversationResponse):
    """Schema for detailed conversation response with messages."""
    messages: List[MessageResponse]


class ConversationListResponse(BaseModel):
    """Schema for list of conversations."""
    items: List[ConversationResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class ConversationFilterParams(BaseModel):
    """Query parameters for filtering conversations."""
    bot_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    visitor_id: Optional[str] = None
    session_id: Optional[str] = None
    min_rating: Optional[int] = None
    max_rating: Optional[int] = None
    has_feedback: Optional[bool] = None
    search_query: Optional[str] = None
    sort_by: Optional[str] = "started_at"
    sort_order: Optional[str] = "desc"
    page: int = 1
    page_size: int = 20


class FeedbackCreate(BaseModel):
    """Schema for creating conversation feedback."""
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ExportFormat(str, Enum):
    """Export format enumeration."""
    CSV = "csv"
    JSON = "json"


class ConversationExportParams(BaseModel):
    """Parameters for exporting conversations."""
    format: ExportFormat = ExportFormat.CSV
    bot_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    include_messages: bool = True
