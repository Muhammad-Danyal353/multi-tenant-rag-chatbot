"""
Template Routes

API endpoints for bot templates:
- CRUD operations for templates
- Creating bots from templates
- Template categories and filtering
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.core.dependencies import (
    get_db, get_current_user, get_current_organization_id,
    require_permission
)
from app.services.template_service import get_template_service
from app.schemas.bot import (
    BotTemplateCreate, BotTemplateResponse, BotTemplateListResponse,
    BotFromTemplateCreate, BotResponse
)
from app.core.exceptions import (
    NotFoundException, ValidationException, ServiceException
)
from app.utils.response import create_response

router = APIRouter()


@router.get("", response_model=BotTemplateListResponse)
async def list_templates(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    featured_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    List available bot templates.
    """
    try:
        service = get_template_service()
        templates, total = service.list_templates(
            db=db,
            limit=limit,
            offset=offset,
            category=category,
            search=search,
            featured_only=featured_only
        )
        
        return create_response(
            data={
                "templates": [template.to_dict() for template in templates],
                "total": total,
                "limit": limit,
                "offset": offset
            },
            message="Templates retrieved successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/categories")
async def get_template_categories(
    db: Session = Depends(get_db)
):
    """
    Get list of template categories with counts.
    """
    try:
        service = get_template_service()
        categories = service.get_template_categories(db=db)
        
        return create_response(
            data={"categories": categories},
            message="Template categories retrieved successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/featured")
async def get_featured_templates(
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """
    Get featured templates.
    """
    try:
        service = get_template_service()
        templates = service.get_featured_templates(
            db=db,
            limit=limit
        )
        
        return create_response(
            data={"templates": [template.to_dict() for template in templates]},
            message="Featured templates retrieved successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{template_id}", response_model=BotTemplateResponse)
async def get_template(
    template_id: str = Path(..., title="Template ID"),
    db: Session = Depends(get_db)
):
    """
    Get template by ID.
    """
    try:
        service = get_template_service()
        template = service.get_template(
            db=db,
            template_id=template_id
        )
        
        return create_response(
            data=template.to_dict(),
            message="Template retrieved successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("", response_model=BotTemplateResponse)
async def create_template(
    template_data: BotTemplateCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new bot template.
    
    Note: This endpoint would typically be restricted to super admins.
    """
    try:
        service = get_template_service()
        template = service.create_template(
            db=db,
            template_data=template_data
        )
        
        return create_response(
            data=template.to_dict(),
            message="Template created successfully"
        )
        
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{template_id}", response_model=BotTemplateResponse)
async def update_template(
    template_data: Dict[str, Any] = Body(...),
    template_id: str = Path(..., title="Template ID"),
    db: Session = Depends(get_db)
):
    """
    Update template information.
    
    Note: This endpoint would typically be restricted to super admins.
    """
    try:
        service = get_template_service()
        template = service.update_template(
            db=db,
            template_id=template_id,
            template_data=template_data
        )
        
        return create_response(
            data=template.to_dict(),
            message="Template updated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{template_id}")
async def delete_template(
    template_id: str = Path(..., title="Template ID"),
    db: Session = Depends(get_db)
):
    """
    Delete a template.
    
    Note: This endpoint would typically be restricted to super admins.
    """
    try:
        service = get_template_service()
        result = service.delete_template(
            db=db,
            template_id=template_id
        )
        
        return create_response(
            data=result,
            message="Template deleted successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/create-bot", response_model=BotResponse)
#@require_permission("bot:create")
async def create_bot_from_template(
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
    try:
        service = get_template_service()
        bot = service.create_bot_from_template(
            db=db,
            organization_id=organization_id,
            user_id=current_user.id,
            template_data=template_data
        )
        
        # Include API key in response (only time it's returned in plaintext)
        response_data = bot.to_dict()
        response_data["api_key"] = bot.api_key
        
        return create_response(
            data=response_data,
            message="Bot created from template successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
