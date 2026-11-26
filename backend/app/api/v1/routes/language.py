"""
Language Routes

API endpoints for multi-language support:
- Get supported languages
- Get/update bot language settings
- Add language translations
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.dependencies import (
    get_db, get_current_organization_id,
    require_permission
)
from app.services.language_service import get_language_service
from app.core.exceptions import (
    NotFoundException, ValidationException, ServiceException
)
from app.utils.response import create_response

router = APIRouter()


@router.get("/languages")
async def get_supported_languages():
    """
    Get list of supported languages.
    """
    try:
        service = get_language_service()
        languages = service.get_supported_languages()
        
        return create_response(
            data={"languages": languages},
            message="Supported languages retrieved successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{bot_id}/languages")
#@require_permission("bot:view")
async def get_bot_languages(
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:view"))
):
    """
    Get language settings for a bot.
    
    Requires:
    - Organization context
    - 'bot:view' permission
    """
    try:
        service = get_language_service()
        language_settings = service.get_bot_languages(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data=language_settings,
            message="Bot language settings retrieved successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{bot_id}/languages")
#@require_permission("bot:edit")
async def update_bot_languages(
    language_settings: Dict[str, Any] = Body(...),
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Update language settings for a bot.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        service = get_language_service()
        bot = service.update_bot_languages(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            language_settings=language_settings
        )
        
        # Get updated language settings
        updated_settings = service.get_bot_languages(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data=updated_settings,
            message="Bot language settings updated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{bot_id}/languages/{language_code}/translations")
#@require_permission("bot:edit")
async def add_language_translations(
    translations: Dict[str, str] = Body(...),
    bot_id: str = Path(..., title="Bot ID"),
    language_code: str = Path(..., title="Language Code"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Add translations for a specific language.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        service = get_language_service()
        bot = service.add_language_translation(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            language_code=language_code,
            translations=translations
        )
        
        # Get language-specific settings
        language_specific = service.get_language_specific_settings(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            language_code=language_code
        )
        
        return create_response(
            data=language_specific,
            message=f"Translations for {language_code} added successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{bot_id}/languages/{language_code}")
#@require_permission("bot:view")
async def get_language_specific_settings(
    bot_id: str = Path(..., title="Bot ID"),
    language_code: str = Path(..., title="Language Code"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:view"))
):
    """
    Get language-specific settings for a bot.
    
    Requires:
    - Organization context
    - 'bot:view' permission
    """
    try:
        service = get_language_service()
        language_specific = service.get_language_specific_settings(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            language_code=language_code
        )
        
        return create_response(
            data=language_specific,
            message=f"Language settings for {language_code} retrieved successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
