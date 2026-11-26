"""
Fallback Routes

API endpoints for fallback responses management:
- Get fallback responses
- Update fallback responses
- Add/delete fallback responses
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_db, get_current_organization_id,
    require_permission
)
from app.services.fallback_service import get_fallback_service
from app.schemas.bot import (
    FallbackResponse, FallbackResponsesUpdate
)
from app.core.exceptions import (
    NotFoundException, ValidationException, ServiceException
)
from app.utils.response import create_response

router = APIRouter()


@router.get("/{bot_id}/fallback-responses")
#@require_permission("bot:view")
async def get_fallback_responses(
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:view"))
):
    """
    Get fallback responses for a bot.
    
    Requires:
    - Organization context
    - 'bot:view' permission
    """
    try:
        service = get_fallback_service()
        responses = service.get_fallback_responses(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data={"responses": responses},
            message="Fallback responses retrieved successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{bot_id}/fallback-responses")
#@require_permission("bot:edit")
async def update_fallback_responses(
    responses_data: FallbackResponsesUpdate,
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Update fallback responses for a bot.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        service = get_fallback_service()
        bot = service.update_fallback_responses(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            responses_data=responses_data
        )
        
        # Get updated responses
        responses = service.get_fallback_responses(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data={"responses": responses},
            message="Fallback responses updated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{bot_id}/fallback-responses")
#@require_permission("bot:edit")
async def add_fallback_response(
    response: FallbackResponse,
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Add a fallback response.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        service = get_fallback_service()
        added_response = service.add_fallback_response(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            response=response
        )
        
        return create_response(
            data=added_response,
            message="Fallback response added successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{bot_id}/fallback-responses/{response_id}")
#@require_permission("bot:edit")
async def delete_fallback_response(
    bot_id: str = Path(..., title="Bot ID"),
    response_id: str = Path(..., title="Response ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Delete a fallback response.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        service = get_fallback_service()
        result = service.delete_fallback_response(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            response_id=response_id
        )
        
        return create_response(
            data=result,
            message="Fallback response deleted successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
