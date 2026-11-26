"""
API v1 Router

Includes all API v1 routes.
"""

from fastapi import APIRouter
from app.api.v1.routes import (
    auth, bots, knowledge_base, chat, analytics, admin, widget,
    suggested_questions, fallback, language, templates, billing,
    conversations, audit, health, organizations, invitations, roles,
    activity, settings, api_keys, domain_allowlist
)

api_router = APIRouter(redirect_slashes=True)

# Auth routes
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# Bot management routes
api_router.include_router(
    bots.router,
    prefix="/bots",
    tags=["Bots"]
)

# Knowledge base routes
api_router.include_router(
    knowledge_base.router,
    prefix="/knowledge",
    tags=["Knowledge Base"]
)

# Chat routes
api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"]
)

# Analytics routes
api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Analytics"]
)

# Admin routes
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin"]
)

# Widget routes
api_router.include_router(
    widget.router,
    prefix="/widget",
    tags=["Widget"]
)

# Suggested questions routes
api_router.include_router(
    suggested_questions.router,
    prefix="/bots",
    tags=["Suggested Questions"]
)

# Fallback responses routes
api_router.include_router(
    fallback.router,
    prefix="/bots",
    tags=["Fallback Responses"]
)

# Language routes
api_router.include_router(
    language.router,
    prefix="/bots",
    tags=["Languages"]
)

# Template routes
api_router.include_router(
    templates.router,
    prefix="/templates",
    tags=["Templates"]
)

# Billing routes
api_router.include_router(
    billing.router,
    prefix="/billing",
    tags=["Billing"]
)

# Conversation management routes
api_router.include_router(
    conversations.router,
    prefix="/conversations",
    tags=["Conversations"]
)

# Audit log routes
api_router.include_router(
    audit.router,
    prefix="/audit",
    tags=["Audit"]
)

# Health check routes
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"]
)

# Organization routes
api_router.include_router(
    organizations.router,
    tags=["Organizations"]
)

# Invitation routes
api_router.include_router(
    invitations.router,
    tags=["Invitations"]
)

# Role management routes
api_router.include_router(
    roles.router,
    tags=["Roles"]
)

# Activity tracking routes
api_router.include_router(
    activity.router,
    tags=["Activity"]
)

# Settings routes
api_router.include_router(
    settings.router,
    tags=["Settings"]
)

# API Keys routes
api_router.include_router(
    api_keys.router,
    tags=["API Keys"]
)

# Domain Allowlist routes
api_router.include_router(
    domain_allowlist.router,
    tags=["Domain Allowlist"]
)
