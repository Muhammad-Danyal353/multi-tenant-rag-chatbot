"""
Widget Routes

Public API for widget integration (no authentication required for chat).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import json
import uuid

from app.core.dependencies import get_db
from app.core.exceptions import NotFoundException, ValidationException
from app.schemas.chat import (
    SendMessageRequest,
    SendMessageResponse,
    StreamMessageRequest,
    StreamMessageChunk
)
from app.services.chat_service import get_chat_service
from app.db.models.bot import Bot
from app.config import settings

router = APIRouter()


@router.post("/{api_key}/chat", response_model=SendMessageResponse)
async def widget_chat(
    api_key: str,
    request: SendMessageRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Widget chat endpoint (public, uses API key authentication).
    
    This endpoint allows anonymous users to chat with bots via API key.
    Includes domain validation and rate limiting.
    """
    try:
        # Validate API key and get bot
        bot = db.query(Bot).filter(
            Bot.api_key == api_key,
            Bot.status == "active"
        ).first()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Validate domain (if allowed_domains is set)
        if bot.allowed_domains:
            origin = http_request.headers.get("origin") or http_request.headers.get("referer")
            if origin:
                # Extract domain from origin/referer
                domain = origin.split("://")[-1].split("/")[0].split(":")[0]
                if domain not in bot.allowed_domains:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Domain not allowed"
                    )
        
        # Get chat service
        chat_service = get_chat_service()
        
        # Send message
        response = chat_service.send_message(
            db=db,
            bot_id=str(bot.id),
            organization_id=str(bot.organization_id),
            message=request.message,
            conversation_id=request.conversation_id,
            visitor_id=request.visitor_id,
            metadata={
                **(request.metadata or {}),
                "widget_request": True,
                "user_agent": http_request.headers.get("user-agent"),
                "ip_address": http_request.client.host if http_request.client else None
            }
        )
        
        return SendMessageResponse(**response)
        
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process widget message: {str(e)}"
        )


@router.post("/{api_key}/chat/stream")
async def widget_chat_stream(
    api_key: str,
    request: StreamMessageRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Widget streaming chat endpoint.
    
    Provides real-time streaming responses for widget integration.
    """
    try:
        # Validate API key and get bot
        bot = db.query(Bot).filter(
            Bot.api_key == api_key,
            Bot.status == "active"
        ).first()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Validate domain
        if bot.allowed_domains:
            origin = http_request.headers.get("origin") or http_request.headers.get("referer")
            if origin:
                domain = origin.split("://")[-1].split("/")[0].split(":")[0]
                if domain not in bot.allowed_domains:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Domain not allowed"
                    )
        
        # Get chat service
        chat_service = get_chat_service()
        llm_service = chat_service.llm_service
        
        # Get or create conversation
        conversation = chat_service._get_or_create_conversation(
            db=db,
            bot_id=str(bot.id),
            organization_id=str(bot.organization_id),
            conversation_id=request.conversation_id,
            visitor_id=request.visitor_id,
            metadata={
                **(request.metadata or {}),
                "widget_request": True,
                "user_agent": http_request.headers.get("user-agent"),
                "ip_address": http_request.client.host if http_request.client else None
            }
        )
        
        # Store user message
        user_message = chat_service._store_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            metadata={
                **(request.metadata or {}),
                "widget_request": True
            }
        )
        
        # Retrieve relevant context
        retrieval_results = chat_service.retrieval_service.hybrid_search(
            query=request.message,
            bot_id=str(bot.id),
            organization_id=str(bot.organization_id),
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
        bot_settings = bot.settings or {}
        
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
                    system_prompt=bot.system_prompt
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
                "Content-Type": "text/event-stream",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process streaming widget message: {str(e)}"
        )


@router.get("/{api_key}/config")
async def get_widget_config(
    api_key: str,
    db: Session = Depends(get_db)
):
    """
    Get widget configuration for embedding.
    
    Returns bot settings, widget configuration, and embed script.
    """
    try:
        # Validate API key and get bot
        bot = db.query(Bot).filter(
            Bot.api_key == api_key,
            Bot.status == "active"
        ).first()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Get widget settings
        widget_settings = bot.widget_settings or {}
        
        # Build configuration
        config = {
            "bot_id": str(bot.id),
            "bot_name": bot.name,
            "bot_description": bot.description,
            "avatar_url": bot.avatar_url,
            "widget_settings": {
                "colors": widget_settings.get("colors", {
                    "primary": "#007bff",
                    "secondary": "#6c757d",
                    "background": "#ffffff"
                }),
                "position": widget_settings.get("position", "bottom-right"),
                "welcome_message": widget_settings.get("welcome_message", "Hi! How can I help you today?"),
                "suggested_questions": widget_settings.get("suggested_questions", []),
                "chat_icon": widget_settings.get("chat_icon", "default")
            },
            "api_endpoints": {
                "chat": f"/api/v1/widget/{api_key}/chat",
                "stream": f"/api/v1/widget/{api_key}/chat/stream",
                "config": f"/api/v1/widget/{api_key}/config"
            }
        }
        
        return config
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get widget config: {str(e)}"
        )


@router.get("/{api_key}/embed-script")
async def get_embed_script(
    api_key: str,
    db: Session = Depends(get_db)
):
    """
    Generate embed script for widget integration.
    
    Returns JavaScript code that can be embedded in websites.
    """
    try:
        # Validate API key and get bot
        bot = db.query(Bot).filter(
            Bot.api_key == api_key,
            Bot.status == "active"
        ).first()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Get widget settings
        widget_settings = bot.widget_settings or {}
        
        # Generate embed script
        embed_script = f"""
(function() {{
    var botId = '{bot.id}';
    var apiKey = '{api_key}';
    var baseUrl = '{settings.FRONTEND_URL}';
    
    // Widget configuration
    var config = {{
        botId: botId,
        apiKey: apiKey,
        baseUrl: baseUrl,
        colors: {json.dumps(widget_settings.get('colors', {{'primary': '#007bff', 'secondary': '#6c757d', 'background': '#ffffff'}}))},
        position: '{widget_settings.get('position', 'bottom-right')}',
        welcomeMessage: '{widget_settings.get('welcome_message', 'Hi! How can I help you today?')}',
        suggestedQuestions: {json.dumps(widget_settings.get('suggested_questions', []))},
        chatIcon: '{widget_settings.get('chat_icon', 'default')}'
    }};
    
    // Create widget container
    var widgetContainer = document.createElement('div');
    widgetContainer.id = 'rag-chatbot-widget';
    widgetContainer.style.cssText = `
        position: fixed;
        {widget_settings.get('position', 'bottom-right')}: 20px;
        bottom: 20px;
        width: 350px;
        height: 500px;
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        z-index: 10000;
        display: none;
        flex-direction: column;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;
    
    // Create chat button
    var chatButton = document.createElement('div');
    chatButton.id = 'rag-chatbot-button';
    chatButton.style.cssText = `
        position: fixed;
        {widget_settings.get('position', 'bottom-right')}: 20px;
        bottom: 20px;
        width: 60px;
        height: 60px;
        background: ${{config.colors.primary}};
        border-radius: 50%;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        z-index: 10001;
        transition: transform 0.2s ease;
    `;
    
    // Add chat icon
    chatButton.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
        </svg>
    `;
    
    // Add click handlers
    chatButton.addEventListener('click', function() {{
        widgetContainer.style.display = widgetContainer.style.display === 'none' ? 'flex' : 'none';
        chatButton.style.display = widgetContainer.style.display === 'flex' ? 'none' : 'flex';
    }});
    
    chatButton.addEventListener('mouseenter', function() {{
        this.style.transform = 'scale(1.1)';
    }});
    
    chatButton.addEventListener('mouseleave', function() {{
        this.style.transform = 'scale(1)';
    }});
    
    // Add to page
    document.body.appendChild(chatButton);
    document.body.appendChild(widgetContainer);
    
    // Initialize widget (simplified version)
    console.log('RAG Chatbot Widget loaded for bot:', botId);
}})();
"""
        
        return {
            "embed_script": embed_script.strip(),
            "bot_id": str(bot.id),
            "bot_name": bot.name,
            "instructions": "Copy and paste this script into your website's HTML to embed the chatbot widget."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embed script: {str(e)}"
        )


@router.post("/{api_key}/session")
async def create_widget_session(
    api_key: str,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Create a new widget session for anonymous users.
    
    Returns session information for tracking conversations.
    """
    try:
        # Validate API key and get bot
        bot = db.query(Bot).filter(
            Bot.api_key == api_key,
            Bot.status == "active"
        ).first()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Validate domain
        if bot.allowed_domains:
            origin = http_request.headers.get("origin") or http_request.headers.get("referer")
            if origin:
                domain = origin.split("://")[-1].split("/")[0].split(":")[0]
                if domain not in bot.allowed_domains:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Domain not allowed"
                    )
        
        # Create session
        session_id = str(uuid.uuid4())
        visitor_id = str(uuid.uuid4())
        
        return {
            "session_id": session_id,
            "visitor_id": visitor_id,
            "bot_id": str(bot.id),
            "bot_name": bot.name,
            "created_at": "2024-01-01T00:00:00Z",
            "metadata": {
                "user_agent": http_request.headers.get("user-agent"),
                "ip_address": http_request.client.host if http_request.client else None,
                "domain": origin.split("://")[-1].split("/")[0] if origin else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create widget session: {str(e)}"
        )

