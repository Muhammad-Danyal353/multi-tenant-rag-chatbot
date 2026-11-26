"""
Conversation Management API Routes

This module defines the FastAPI routes for conversation management.
"""

import csv
import json
import io
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, asc, or_, and_, func, text
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.db.session import get_db, get_async_db
from app.core.dependencies import get_current_user, require_permission
from app.schemas.auth import UserResponse
from app.schemas.conversation import (
    ConversationResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    FeedbackCreate,
    ExportFormat,
    MessageResponse
)
from app.schemas.base import ApiResponse
from app.utils.response import create_response
from app.db.models.conversation import Conversation, Message
from app.db.models.bot import Bot
from app.services.analytics_service import get_analytics_service, AnalyticsService

router = APIRouter()


@router.get(
    "/{organization_id}",
    response_model=ApiResponse[ConversationListResponse],
    summary="List and search conversations"
)
async def list_conversations(
    organization_id: str,
    bot_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    visitor_id: Optional[str] = None,
    session_id: Optional[str] = None,
    min_rating: Optional[int] = None,
    max_rating: Optional[int] = None,
    has_feedback: Optional[bool] = None,
    search_query: Optional[str] = None,
    sort_by: str = "started_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List and search conversations for the organization.
    
    Supports filtering by various parameters and full-text search.
    """
    # Check permissions
    require_permission(current_user, "conversations:view", organization_id=organization_id)
    
    # Validate page parameters
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20
    
    # Base query conditions
    conditions = [Conversation.organization_id == organization_id]
    
    # Apply filters
    if bot_id:
        conditions.append(Conversation.bot_id == bot_id)
    
    if start_date:
        conditions.append(Conversation.started_at >= start_date)
    
    if end_date:
        conditions.append(Conversation.started_at <= end_date)
    
    if visitor_id:
        conditions.append(Conversation.visitor_id == visitor_id)
    
    if session_id:
        conditions.append(Conversation.session_id == session_id)
    
    if min_rating is not None:
        conditions.append(Conversation.rating >= min_rating)
    
    if max_rating is not None:
        conditions.append(Conversation.rating <= max_rating)
    
    if has_feedback is not None:
        if has_feedback:
            conditions.append(Conversation.feedback.isnot(None))
        else:
            conditions.append(Conversation.feedback.is_(None))
    
    # Add search query if provided
    if search_query:
        # Join with messages to search in message content
        message_subquery = (
            select(Message.conversation_id)
            .where(Message.content.ilike(f"%{search_query}%"))
            .distinct()
            .subquery()
        )
        
        conditions.append(
            or_(
                Conversation.id.in_(message_subquery),
                Conversation.feedback.ilike(f"%{search_query}%"),
                Conversation.metadata.cast(text("text")).ilike(f"%{search_query}%")
            )
        )
    
    # Determine sort order
    if sort_by not in ["started_at", "ended_at", "duration", "rating"]:
        sort_by = "started_at"
    
    sort_column = getattr(Conversation, sort_by)
    if sort_order.lower() == "asc":
        sort_column = asc(sort_column)
    else:
        sort_column = desc(sort_column)
    
    # Count total matching conversations
    count_stmt = select(func.count()).select_from(Conversation).where(*conditions)
    result = await db.execute(count_stmt)
    total_count = result.scalar_one()
    
    # Calculate pagination
    offset = (page - 1) * page_size
    has_more = total_count > offset + page_size
    
    # Query conversations with pagination
    stmt = (
        select(Conversation)
        .where(*conditions)
        .order_by(sort_column)
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    conversations =  result.scalars().all()
    
    # Format response
    return create_response(
        data={
            "items": conversations,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": has_more
        },
        message="Conversations retrieved successfully"
    )


@router.get(
    "/{organization_id}/{conversation_id}",
    response_model=ApiResponse[ConversationDetailResponse],
    summary="Get conversation details with messages"
)
async def get_conversation(
    organization_id: str,
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get detailed conversation information including all messages.
    """
    # Check permissions
    require_permission(current_user, "conversations:view", organization_id=organization_id)
    
    # Query conversation
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.organization_id == organization_id
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found"
        )
    
    # Query messages
    stmt = select(Message).where(
        Message.conversation_id == conversation_id
    ).order_by(Message.timestamp)
    result = await db.execute(stmt)
    messages =  result.scalars().all()
    
    # Format response
    response = ConversationDetailResponse.from_orm(conversation)
    response.messages = messages
    
    return create_response(
        data=response,
        message="Conversation details retrieved successfully"
    )


@router.post(
    "/{organization_id}/{conversation_id}/feedback",
    response_model=ApiResponse[ConversationResponse],
    summary="Submit feedback for a conversation"
)
async def submit_feedback(
    organization_id: str,
    conversation_id: str,
    feedback: FeedbackCreate,
    current_user: UserResponse = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Submit a rating and optional feedback for a conversation.
    """
    # Check permissions
    require_permission(current_user, "conversations:feedback", organization_id=organization_id)
    
    # Query conversation
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.organization_id == organization_id
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found"
        )
    
    # Update conversation with feedback
    conversation.rating = feedback.rating
    conversation.feedback = feedback.feedback
    
    if feedback.metadata:
        # Merge metadata
        if conversation.metadata:
            conversation.metadata.update(feedback.metadata)
        else:
            conversation.metadata = feedback.metadata
    
    await db.commit()
    
    # Track feedback event
    await analytics_service.track_event(
        organization_id=organization_id,
        event_type="conversation_feedback",
        event_data={
            "conversation_id": conversation_id,
            "rating": feedback.rating,
            "feedback": feedback.feedback,
            "bot_id": conversation.bot_id
        },
        bot_id=conversation.bot_id,
        user_id=current_user.id,
        db=db
    )
    
    return create_response(
        data=conversation,
        message="Feedback submitted successfully"
    )


@router.get(
    "/{organization_id}/export",
    summary="Export conversations as CSV or JSON"
)
async def export_conversations(
    organization_id: str,
    format: ExportFormat = ExportFormat.CSV,
    bot_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_messages: bool = True,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Export conversations as CSV or JSON.
    
    Supports filtering by bot, date range, and including messages.
    """
    # Check permissions
    require_permission(current_user, "conversations:export", organization_id=organization_id)
    
    # Base query conditions
    conditions = [Conversation.organization_id == organization_id]
    
    # Apply filters
    if bot_id:
        conditions.append(Conversation.bot_id == bot_id)
    
    if start_date:
        conditions.append(Conversation.started_at >= start_date)
    
    if end_date:
        conditions.append(Conversation.started_at <= end_date)
    
    # Query conversations
    stmt = select(Conversation).where(*conditions).order_by(desc(Conversation.started_at))
    result = await db.execute(stmt)
    conversations =  result.scalars().all()
    
    # Format for export
    export_data = []
    for conv in conversations:
        conv_data = {
            "id": conv.id,
            "bot_id": conv.bot_id,
            "organization_id": conv.organization_id,
            "session_id": conv.session_id,
            "visitor_id": conv.visitor_id,
            "started_at": conv.started_at.isoformat() if conv.started_at else None,
            "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
            "duration": conv.duration,
            "rating": conv.rating,
            "feedback": conv.feedback
        }
        
        # Include messages if requested
        if include_messages:
            # Query messages for this conversation
            stmt = select(Message).where(
                Message.conversation_id == conv.id
            ).order_by(Message.timestamp)
            result = await db.execute(stmt)
            messages =  result.scalars().all()
            
            # Format messages
            conv_data["messages"] = []
            for msg in messages:
                msg_data = {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    "latency_ms": msg.latency_ms,
                    "token_count": msg.token_count
                }
                conv_data["messages"].append(msg_data)
        
        export_data.append(conv_data)
    
    # Generate export file
    if format == ExportFormat.JSON:
        # JSON export
        json_data = json.dumps(export_data, indent=2)
        
        # Create a StringIO object
        output = io.StringIO()
        output.write(json_data)
        output.seek(0)
        
        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"conversations_export_{timestamp}.json"
        
        # Return streaming response
        return StreamingResponse(
            output,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    else:
        # CSV export
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        header = [
            "id", "bot_id", "organization_id", "session_id", "visitor_id",
            "started_at", "ended_at", "duration", "rating", "feedback"
        ]
        
        if include_messages:
            header.extend(["message_id", "message_role", "message_content", "message_timestamp"])
        
        writer.writerow(header)
        
        # Write data
        for conv in export_data:
            if include_messages and conv.get("messages"):
                # Write a row for each message
                for msg in conv["messages"]:
                    row = [
                        conv["id"], conv["bot_id"], conv["organization_id"],
                        conv["session_id"], conv["visitor_id"], conv["started_at"],
                        conv["ended_at"], conv["duration"], conv["rating"], conv["feedback"],
                        msg["id"], msg["role"], msg["content"], msg["timestamp"]
                    ]
                    writer.writerow(row)
            else:
                # Write a single row for the conversation
                row = [
                    conv["id"], conv["bot_id"], conv["organization_id"],
                    conv["session_id"], conv["visitor_id"], conv["started_at"],
                    conv["ended_at"], conv["duration"], conv["rating"], conv["feedback"]
                ]
                writer.writerow(row)
        
        output.seek(0)
        
        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"conversations_export_{timestamp}.csv"
        
        # Return streaming response
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
