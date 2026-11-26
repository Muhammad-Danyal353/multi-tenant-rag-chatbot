"""
Chat Routes

Handles chat conversations and messages.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import json

from app.core.dependencies import get_db, get_current_user, get_current_organization_id, require_permission
from app.core.exceptions import NotFoundException, ValidationException
from app.schemas.chat import (
    SendMessageRequest,
    SendMessageResponse,
    ConversationResponse,
    ListConversationsResponse,
    SubmitFeedbackRequest,
    SubmitFeedbackResponse,
    StreamMessageRequest,
    StreamMessageChunk,
    SearchRequest,
    SearchResponse
)
from app.schemas.base import ApiResponse
from app.services.chat_service import get_chat_service
from app.services.retrieval_service import get_retrieval_service
from app.db.models.user import User
from app.config import settings
from app.utils.response import create_response

router = APIRouter()


@router.post("/{bot_id}/message", response_model=ApiResponse[SendMessageResponse])
async def send_message(
    bot_id: str,
    request: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_current_organization_id)
):
    """
    Send a message to a bot and get AI response.
    
    This endpoint processes user messages and returns AI responses with source attribution.
    """
    try:
        chat_service = get_chat_service()
        
        # organization_id is now properly obtained from dependency
        
        # Send message and get response
        response = chat_service.send_message(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            message=request.message,
            conversation_id=request.conversation_id,
            visitor_id=request.visitor_id,
            metadata=request.metadata
        )
        
        return create_response(
            data=SendMessageResponse(**response),
            message="Message processed successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )


@router.post("/{bot_id}/message/stream")
async def send_message_stream(
    bot_id: str,
    request: StreamMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_current_organization_id)
):
    """
    Send a message to a bot and get streaming AI response.
    
    This endpoint provides real-time streaming responses using Server-Sent Events (SSE).
    """
    try:
        chat_service = get_chat_service()
        llm_service = chat_service.llm_service
        
        # organization_id is now properly obtained from dependency
        
        # Get or create conversation
        conversation = chat_service._get_or_create_conversation(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            conversation_id=request.conversation_id,
            visitor_id=request.visitor_id,
            metadata=request.metadata
        )
        
        # Store user message
        user_message = chat_service._store_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            metadata=request.metadata
        )
        
        # Retrieve relevant context
        retrieval_results = chat_service.retrieval_service.hybrid_search(
            query=request.message,
            bot_id=bot_id,
            organization_id=organization_id,
            top_k=settings.DEFAULT_TOP_K
        )
        
        # Get conversation context
        context_messages = chat_service._get_conversation_context(
            db=db,
            conversation_id=conversation.id,
            max_messages=chat_service.max_context_messages
        )
        
        # Format knowledge context
        knowledge_context = chat_service._format_knowledge_context(retrieval_results)
        
        # Get bot settings
        from app.db.models.bot import Bot
        bot = db.query(Bot).filter(Bot.id == bot_id).first()
        bot_settings = bot.settings or {} if bot else {}
        
        async def generate_stream():
            """Generate streaming response."""
            try:
                # Send conversation metadata
                yield f"data: {json.dumps(StreamMessageChunk(type='metadata', data={'conversation_id': str(conversation.id), 'message_id': str(user_message.id)}, conversation_id=str(conversation.id), message_id=str(user_message.id)).dict())}\n\n"
                
                # Send sources
                sources = chat_service.retrieval_service.get_source_attribution(retrieval_results)
                yield f"data: {json.dumps(StreamMessageChunk(type='sources', data=sources, conversation_id=str(conversation.id)).dict())}\n\n"
                
                # Stream AI response
                response_content = ""
                async for chunk in llm_service.generate_response_stream(
                    user_message=request.message,
                    context_messages=context_messages,
                    knowledge_context=knowledge_context,
                    bot_settings=bot_settings,
                    system_prompt=bot.system_prompt if bot else None
                ):
                    response_content += chunk
                    yield f"data: {json.dumps(StreamMessageChunk(type='content', data=chunk, conversation_id=str(conversation.id)).dict())}\n\n"
                
                # Store AI message
                ai_message = chat_service._store_message(
                    db=db,
                    conversation_id=conversation.id,
                    role="assistant",
                    content=response_content,
                    sources_used=[r["id"] for r in retrieval_results]
                )
                
                # Send completion
                yield f"data: {json.dumps(StreamMessageChunk(type='complete', data={'message_id': str(ai_message.id)}, conversation_id=str(conversation.id), message_id=str(ai_message.id)).dict())}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps(StreamMessageChunk(type='error', data=str(e), conversation_id=str(conversation.id)).dict())}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process streaming message: {str(e)}"
        )


@router.get("/conversations", response_model=ApiResponse[ListConversationsResponse])
async def list_conversations(
    bot_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_current_organization_id)
):
    """
    List conversations for the current user's organization.
    
    Supports filtering by bot and pagination.
    """
    try:
        chat_service = get_chat_service()
        
        # organization_id is now properly obtained from dependency
        
        # List conversations
        response = chat_service.list_conversations(
            db=db,
            organization_id=organization_id,
            bot_id=bot_id,
            limit=limit,
            offset=offset
        )
        
        return create_response(
            data=ListConversationsResponse(**response),
            message="Conversations retrieved successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.get("/conversations/{conversation_id}", response_model=ApiResponse[ConversationResponse])
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_current_organization_id)
):
    """
    Get conversation details and messages.
    
    Returns full conversation history with all messages.
    """
    try:
        chat_service = get_chat_service()
        
        # organization_id is now properly obtained from dependency
        
        # Get conversation
        conversation = chat_service.get_conversation(
            db=db,
            conversation_id=conversation_id,
            organization_id=organization_id
        )
        
        return create_response(
            data=ConversationResponse(**conversation),
            message="Conversation retrieved successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation: {str(e)}"
        )


@router.post("/conversations/{conversation_id}/feedback", response_model=ApiResponse[SubmitFeedbackResponse])
async def submit_feedback(
    conversation_id: str,
    request: SubmitFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_current_organization_id)
):
    """
    Submit feedback for a conversation.
    
    Allows users to rate conversations and provide optional text feedback.
    """
    try:
        chat_service = get_chat_service()
        
        # organization_id is now properly obtained from dependency
        
        # Submit feedback
        response = chat_service.submit_feedback(
            db=db,
            conversation_id=conversation_id,
            organization_id=organization_id,
            rating=request.rating,
            feedback=request.feedback
        )
        
        return create_response(
            data=SubmitFeedbackResponse(**response),
            message="Feedback submitted successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )


@router.post("/{bot_id}/search", response_model=ApiResponse[SearchResponse])
async def search_knowledge_base(
    bot_id: str,
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_current_organization_id)
):
    """
    Search the knowledge base for a specific bot.
    
    Performs hybrid search (vector + BM25) on the bot's knowledge base.
    """
    try:
        retrieval_service = get_retrieval_service()
        
        # organization_id is now properly obtained from dependency
        
        # Perform search
        results = retrieval_service.hybrid_search(
            query=request.query,
            bot_id=bot_id,
            organization_id=organization_id,
            top_k=request.top_k,
            filters=request.filters,
            source_types=request.source_types
        )
        
        # Format response
        from datetime import datetime
        response = {
            "results": results,
            "total": len(results),
            "query": request.query,
            "latency_ms": 0  # Could be measured if needed
        }
        
        return create_response(
            data=SearchResponse(**response),
            message="Search completed successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search knowledge base: {str(e)}"
        )

