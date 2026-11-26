"""
Database Models Package

Exports all SQLAlchemy models for the application.
"""

from app.db.models.user import User
from app.db.models.organization import Organization, Membership, MemberRole, SubscriptionPlan as OrgSubscriptionPlan, SubscriptionStatus as OrgSubscriptionStatus
from app.db.models.bot import Bot, BotStatus
from app.db.models.api_key import ApiKey
from app.db.models.knowledge_base import (
    KnowledgeSource,
    Document,
    WebPage,
    TextContent,
    Chunk,
    SourceType,
    SourceStatus
)
from app.db.models.conversation import Conversation, Message, MessageRole
from app.db.models.event import Event
from app.db.models.subscription import Plan, Subscription, UsageCounter, PlanType, SubscriptionStatus
from app.db.models.audit_log import AuditLog


# Export all models
__all__ = [
    # User models
    "User",
    
    # Organization models
    "Organization",
    "Membership",
    "MemberRole",
    "OrgSubscriptionPlan",
    "OrgSubscriptionStatus",
    
    # Bot models
    "Bot",
    "BotStatus",
    "ApiKey",
    
    # Knowledge base models
    "KnowledgeSource",
    "Document",
    "WebPage",
    "TextContent",
    "Chunk",
    "SourceType",
    "SourceStatus",
    
    # Conversation models
    "Conversation",
    "Message",
    "Event",
    "MessageRole",
    
    # Subscription models
    "Plan",
    "Subscription",
    "UsageCounter",
    "PlanType",
    "SubscriptionStatus",
    
    # Audit models
    "AuditLog",
]

