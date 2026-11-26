"""
Bot Routes

API endpoints for bot management:
- CRUD operations for bots
- API key management
- Widget customization
- Bot templates
- Suggested questions
- Fallback responses
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.dependencies import (
    get_db, get_current_user, get_current_organization_id,
    require_permission
)
from app.services.bot_service import get_bot_service
from app.schemas.bot import (
    BotCreate, BotUpdate, BotResponse, BotDetailResponse, BotListResponse,
    BotSettingsUpdate, WidgetSettingsUpdate, APIKeyResponse,
    SuggestedQuestionsUpdate, FallbackResponsesUpdate, BotCloneRequest,
    BotTemplateListResponse, BotTemplateCreate, BotTemplateResponse,
    BotFromTemplateCreate
)
from app.schemas.base import ApiResponse
from app.core.exceptions import (
    NotFoundException, ValidationException, DuplicateException,
    ServiceException
)
from app.utils.response import create_response

router = APIRouter()


@router.post("", response_model=ApiResponse[BotResponse])
#@require_permission("bot:create")
async def create_bot(
    bot_data: BotCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:create"))
):
    """
    Create a new bot.
    
    Requires:
    - Organization context
    - 'bot:create' permission
    """
    try:
        bot_service = get_bot_service()
        bot = bot_service.create_bot(
            db=db,
            organization_id=organization_id,
            user_id=current_user.id,
            bot_data=bot_data
        )
        
        # Include API key in response (only time it's returned in plaintext)
        response_data = bot.to_dict()
        response_data["api_key"] = bot.api_key
        
        return create_response(
            data=response_data,
            message="Bot created successfully"
        )
        
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=ApiResponse[BotListResponse])
#@require_permission("bot:view")
async def list_bots(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:view"))
):
    """
    List bots for the current organization.
    
    Requires:
    - Organization context
    - 'bot:view' permission
    """
    try:
        bot_service = get_bot_service()
        bots, total = bot_service.list_bots(
            db=db,
            organization_id=organization_id,
            limit=limit,
            offset=offset,
            status=status,
            search=search
        )
        
        return create_response(
            data={
                "bots": [bot.to_dict() for bot in bots],
                "total": total,
                "limit": limit,
                "offset": offset
            },
            message="Bots retrieved successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{bot_id}", response_model=ApiResponse[BotDetailResponse])
#@require_permission("bot:view")
async def get_bot(
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:view"))
):
    """
    Get detailed bot information.
    
    Requires:
    - Organization context
    - 'bot:view' permission
    """
    try:
        bot_service = get_bot_service()
        bot_detail = bot_service.get_bot_detail(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data=bot_detail,
            message="Bot retrieved successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{bot_id}", response_model=ApiResponse[BotResponse])
#@require_permission("bot:edit")
async def update_bot(
    bot_data: BotUpdate,
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Update bot information.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        bot_service = get_bot_service()
        bot = bot_service.update_bot(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            bot_data=bot_data
        )
        
        return create_response(
            data=bot.to_dict(),
            message="Bot updated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{bot_id}")
#@require_permission("bot:delete")
async def delete_bot(
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:delete"))
):
    """
    Delete a bot.
    
    Requires:
    - Organization context
    - 'bot:delete' permission
    """
    try:
        bot_service = get_bot_service()
        result = bot_service.delete_bot(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data=result,
            message="Bot deleted successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{bot_id}/settings", response_model=ApiResponse[BotResponse])
#@require_permission("bot:edit")
async def update_bot_settings(
    settings_data: BotSettingsUpdate,
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Update bot behavior settings.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        bot_service = get_bot_service()
        bot = bot_service.update_bot_settings(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            settings_data=settings_data
        )
        
        return create_response(
            data=bot.to_dict(),
            message="Bot settings updated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{bot_id}/widget", response_model=ApiResponse[BotResponse])
#@require_permission("bot:edit")
async def update_widget_settings(
    widget_data: WidgetSettingsUpdate,
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Update widget appearance settings.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        bot_service = get_bot_service()
        bot = bot_service.update_widget_settings(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            widget_data=widget_data
        )
        
        return create_response(
            data=bot.to_dict(),
            message="Widget settings updated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{bot_id}/api-keys", response_model=ApiResponse[APIKeyResponse])
#@require_permission("bot:edit")
async def generate_api_key(
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Generate a new API key for a bot.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        bot_service = get_bot_service()
        result = bot_service.generate_api_key(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data=result,
            message="API key generated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{bot_id}/suggested-questions", response_model=ApiResponse[BotResponse])
#@require_permission("bot:edit")
async def update_suggested_questions(
    questions_data: SuggestedQuestionsUpdate,
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Update suggested questions for a bot.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        bot_service = get_bot_service()
        bot = bot_service.update_suggested_questions(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            questions_data=questions_data
        )
        
        return create_response(
            data=bot.to_dict(),
            message="Suggested questions updated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{bot_id}/fallback-responses", response_model=ApiResponse[BotResponse])
#@require_permission("bot:edit")
async def update_fallback_responses(
    responses_data: FallbackResponsesUpdate,
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:create"))
):
    """
    Update fallback responses for a bot.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        bot_service = get_bot_service()
        bot = bot_service.update_fallback_responses(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            responses_data=responses_data
        )
        
        return create_response(
            data=bot.to_dict(),
            message="Fallback responses updated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{bot_id}/clone", response_model=ApiResponse[BotResponse])
#@require_permission("bot:create")
async def clone_bot(
    clone_data: BotCloneRequest,
    bot_id: str = Path(..., title="Bot ID to clone"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    current_user = Depends(get_current_user)
):
    """
    Clone a bot.
    
    Requires:
    - Organization context
    - 'bot:create' permission
    """
    try:
        bot_service = get_bot_service()
        bot = bot_service.clone_bot(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            user_id=current_user.id,
            clone_data=clone_data
        )
        
        # Include API key in response (only time it's returned in plaintext)
        response_data = bot.to_dict()
        response_data["api_key"] = bot.api_key
        
        return create_response(
            data=response_data,
            message="Bot cloned successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{bot_id}/embed-script")
#@require_permission("bot:view")
async def get_embed_script(
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:view"))
):
    """
    Get embed script for a bot.
    
    Requires:
    - Organization context
    - 'bot:view' permission
    """
    try:
        bot_service = get_bot_service()
        bot = bot_service.get_bot(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        # Generate embed script
        embed_script = bot.get_widget_script()
        
        return create_response(
            data={
                "bot_id": bot_id,
                "embed_script": embed_script,
                "instructions": "Copy and paste this script into your website's HTML to embed the chatbot widget."
            },
            message="Embed script generated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ============================================================================
# BOT TEMPLATES
# ============================================================================

@router.get("/templates", response_model=ApiResponse[BotTemplateListResponse])
#@require_permission("bot:view")
async def list_templates(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _ :bool= Depends(require_permission("bot:view"))
):
    """
    List available bot templates.
    
    Requires:
    - Organization context
    - 'bot:view' permission
    """
    # This would be implemented to list templates from a database
    # For now, return a mock response with some templates
    
    templates = [
        {
            "id": "template-1",
            "name": "Customer Support Bot",
            "description": "A bot designed to handle customer support inquiries",
            "category": "support",
            "settings": {
                "tone": "friendly",
                "temperature": 0.7,
                "max_tokens": 500,
                "model": "gpt-3.5-turbo",
                "confidence_threshold": 0.7
            },
            "widget_settings": {
                "colors": {
                    "primary": "#007bff",
                    "secondary": "#6c757d",
                    "background": "#ffffff"
                },
                "position": "bottom-right",
                "welcome_message": "Hi! How can I help you today?"
            },
            "system_prompt": "You are a helpful customer support assistant...",
            "suggested_questions": [
                "How do I reset my password?",
                "What are your business hours?",
                "How do I contact support?"
            ],
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z"
        },
        {
            "id": "template-2",
            "name": "Sales Assistant",
            "description": "A bot designed to assist with sales inquiries",
            "category": "sales",
            "settings": {
                "tone": "professional",
                "temperature": 0.5,
                "max_tokens": 600,
                "model": "gpt-4",
                "confidence_threshold": 0.8
            },
            "widget_settings": {
                "colors": {
                    "primary": "#28a745",
                    "secondary": "#6c757d",
                    "background": "#ffffff"
                },
                "position": "bottom-right",
                "welcome_message": "Hello! Interested in learning more about our products?"
            },
            "system_prompt": "You are a knowledgeable sales assistant...",
            "suggested_questions": [
                "What products do you offer?",
                "Can I get a demo?",
                "What are your pricing plans?"
            ],
            "created_at": "2023-01-02T00:00:00Z",
            "updated_at": "2023-01-02T00:00:00Z"
        }
    ]
    
    # Filter by category if provided
    if category:
        templates = [t for t in templates if t["category"] == category]
    
    # Apply pagination
    total = len(templates)
    templates = templates[offset:offset + limit]
    
    return create_response(
        data={
            "templates": templates,
            "total": total,
            "limit": limit,
            "offset": offset
        },
        message="Templates retrieved successfully"
    )


@router.post("/from-template", response_model=ApiResponse[BotResponse])
#@require_permission("bot:create")
async def create_from_template(
    template_data: BotFromTemplateCreate,
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    current_user = Depends(get_current_user),
    _ :bool= Depends(require_permission("bot:create"))
):
    """
    Create a bot from a template.
    
    Requires:
    - Organization context
    - 'bot:create' permission
    """
    # This would be implemented to create a bot from a template
    # For now, create a basic bot with template settings
    
    try:
        # Mock template data
        templates = {
            "template-1": {
                "name": "Customer Support Bot",
                "description": "A bot designed to handle customer support inquiries",
                "settings": {
                    "tone": "friendly",
                    "temperature": 0.7,
                    "max_tokens": 500,
                    "model": "gpt-3.5-turbo",
                    "system_prompt": "You are a helpful customer support assistant...",
                    "confidence_threshold": 0.7
                },
                "widget_settings": {
                    "colors": {
                        "primary": "#007bff",
                        "secondary": "#6c757d",
                        "background": "#ffffff"
                    },
                    "position": "bottom-right",
                    "welcome_message": "Hi! How can I help you today?",
                    "suggested_questions": [
                        "How do I reset my password?",
                        "What are your business hours?",
                        "How do I contact support?"
                    ]
                }
            },
            "template-2": {
                "name": "Sales Assistant",
                "description": "A bot designed to assist with sales inquiries",
                "settings": {
                    "tone": "professional",
                    "temperature": 0.5,
                    "max_tokens": 600,
                    "model": "gpt-4",
                    "system_prompt": "You are a knowledgeable sales assistant...",
                    "confidence_threshold": 0.8
                },
                "widget_settings": {
                    "colors": {
                        "primary": "#28a745",
                        "secondary": "#6c757d",
                        "background": "#ffffff"
                    },
                    "position": "bottom-right",
                    "welcome_message": "Hello! Interested in learning more about our products?",
                    "suggested_questions": [
                        "What products do you offer?",
                        "Can I get a demo?",
                        "What are your pricing plans?"
                    ]
                }
            }
        }
        
        # Check if template exists
        if template_data.template_id not in templates:
            raise NotFoundException(f"Template {template_data.template_id} not found")
        
        # Get template
        template = templates[template_data.template_id]
        
        # Create bot data
        bot_data = BotCreate(
            name=template_data.name,
            description=template_data.description or template["description"],
            status="draft",
            settings=template["settings"],
            widget_settings=template["widget_settings"]
        )
        
        # Create bot
        bot_service = get_bot_service()
        bot = bot_service.create_bot(
            db=db,
            organization_id=organization_id,
            user_id=current_user.id,
            bot_data=bot_data
        )
        
        # Include API key in response (only time it's returned in plaintext)
        response_data = bot.to_dict()
        response_data["api_key"] = bot.api_key
        
        return create_response(
            data=response_data,
            message=f"Bot created from template '{template['name']}' successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))