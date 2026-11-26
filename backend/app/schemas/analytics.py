"""
Analytics Schemas

This module defines Pydantic models for analytics data.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class DateRange(BaseModel):
    """Date range for filtering analytics data."""
    start: str
    end: str


class ConversationTrend(BaseModel):
    """Daily conversation count for trend analysis."""
    date: str
    count: int


class DurationDistribution(BaseModel):
    """Conversation duration distribution bucket."""
    name: str
    count: int


class HourlyVolume(BaseModel):
    """Conversation volume by hour of day."""
    hour: int
    count: int


class TopQuery(BaseModel):
    """Top user query."""
    query: str
    count: int


class SourceUsage(BaseModel):
    """Knowledge source usage metrics."""
    id: str
    name: str
    type: str
    usage_count: int


class SourceCoverage(BaseModel):
    """Source coverage metrics."""
    total_messages: int
    messages_with_sources: int
    coverage_percentage: float


class OverviewMetrics(BaseModel):
    """Overview metrics for the analytics dashboard."""
    total_conversations: int
    total_messages: int
    avg_messages_per_conversation: float
    avg_response_time_ms: float
    satisfaction_score: int
    avg_rating: float
    total_ratings: int
    positive_ratings: int
    negative_ratings: int
    active_bots: int
    total_knowledge_sources: int
    conversation_trend: List[ConversationTrend]
    date_range: DateRange


class ConversationAnalytics(BaseModel):
    """Conversation analytics data."""
    total_conversations: int
    avg_duration_seconds: float
    rated_conversations: int
    avg_rating: float
    duration_distribution: List[DurationDistribution]
    volume_by_hour: List[HourlyVolume]
    top_queries: List[TopQuery]
    date_range: DateRange


class SourceAnalytics(BaseModel):
    """Knowledge source analytics data."""
    source_usage: List[SourceUsage]
    source_coverage: SourceCoverage
    date_range: DateRange


class EventCreate(BaseModel):
    """Schema for creating an analytics event."""
    event_type: str
    event_data: Dict[str, Any]
    bot_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class EventResponse(BaseModel):
    """Schema for event response."""
    id: str
    organization_id: str
    event_type: str
    event_data: Dict[str, Any]
    bot_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True


class AnalyticsFilterParams(BaseModel):
    """Query parameters for filtering analytics data."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bot_id: Optional[str] = None
