from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db, get_async_db
from app.core.dependencies import get_current_user, require_permission
from app.db.models.user import User
from app.services.api_key_service import APIKeyService
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyListResponse,
    APIKeyDetail
)
from app.core.exceptions import NotFoundException, ConflictException, ForbiddenException

router = APIRouter(prefix="/bots", tags=["API Keys"])

@router.post(
    "/{bot_id}/api-keys",
    response_model=APIKeyDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new API key for a bot"
)
async def create_api_key(
    bot_id: str = Path(..., description="Bot ID"),
    data: APIKeyCreate = ...,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a new API key for the specified bot.
    
    - **bot_id**: The ID of the bot to generate an API key for.
    - **name**: Optional name/description for the API key.
    - **expires_in_days**: Optional number of days until the key expires.
    """
    try:
        # Check if user has permission to manage API keys for this bot
        org_id = await get_bot_organization_id(db, bot_id)
        await require_permission("bot:manage_api_keys")(current_user, org_id, db)
        
        service = APIKeyService(db)
        
        # Calculate expiration date if provided
        expires_at = None
        if data.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)
            
        api_key_obj, plain_key = await service.create_api_key(
            bot_id=bot_id,
            organization_id=org_id,
            created_by_user_id=current_user.id,
            name=data.name,
            expires_at=expires_at
        )
        
        # Return both the API key object and the plain text key
        # The plain text key will only be shown once
        return {
            "id": api_key_obj.id,
            "bot_id": api_key_obj.bot_id,
            "name": api_key_obj.name,
            "created_at": api_key_obj.created_at,
            "expires_at": api_key_obj.expires_at,
            "is_active": api_key_obj.is_active,
            "key": plain_key  # This is the only time the plain key will be returned
        }
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/{bot_id}/api-keys",
    response_model=APIKeyListResponse,
    summary="List API keys for a bot"
)
async def list_api_keys(
    bot_id: str = Path(..., description="Bot ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all API keys for a specific bot.
    
    - **bot_id**: The ID of the bot.
    - **is_active**: Optional filter to show only active or inactive API keys.
    """
    try:
        # Check if user has permission to view API keys for this bot
        org_id = await get_bot_organization_id(db, bot_id)
        await require_permission("bot:view_api_keys")(current_user, org_id, db)
        
        service = APIKeyService(db)
        api_keys, total = await service.list_api_keys(
            bot_id=bot_id,
            organization_id=org_id,
            is_active=is_active,
            skip=skip,
            limit=limit
        )
        
        return {"items": api_keys, "total": total}
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete(
    "/{bot_id}/api-keys/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key"
)
async def revoke_api_key(
    bot_id: str = Path(..., description="Bot ID"),
    api_key_id: str = Path(..., description="API Key ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revoke an API key for a bot.
    
    - **bot_id**: The ID of the bot.
    - **api_key_id**: The ID of the API key to revoke.
    """
    try:
        # Check if user has permission to manage API keys for this bot
        org_id = await get_bot_organization_id(db, bot_id)
        await require_permission("bot:manage_api_keys")(current_user, org_id, db)
        
        service = APIKeyService(db)
        await service.revoke_api_key(
            api_key_id=api_key_id,
            bot_id=bot_id,
            organization_id=org_id
        )
        
        return None
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post(
    "/{bot_id}/api-keys/{api_key_id}/rotate",
    response_model=APIKeyDetail,
    summary="Rotate an API key"
)
async def rotate_api_key(
    bot_id: str = Path(..., description="Bot ID"),
    api_key_id: str = Path(..., description="API Key ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rotate an API key by revoking the old one and creating a new one.
    
    - **bot_id**: The ID of the bot.
    - **api_key_id**: The ID of the API key to rotate.
    """
    try:
        # Check if user has permission to manage API keys for this bot
        org_id = await get_bot_organization_id(db, bot_id)
        await require_permission("bot:manage_api_keys")(current_user, org_id, db)
        
        service = APIKeyService(db)
        new_api_key_obj, plain_key = await service.rotate_api_key(
            api_key_id=api_key_id,
            bot_id=bot_id,
            organization_id=org_id,
            created_by_user_id=current_user.id
        )
        
        return {
            "id": new_api_key_obj.id,
            "bot_id": new_api_key_obj.bot_id,
            "name": new_api_key_obj.name,
            "created_at": new_api_key_obj.created_at,
            "expires_at": new_api_key_obj.expires_at,
            "is_active": new_api_key_obj.is_active,
            "key": plain_key  # This is the only time the plain key will be returned
        }
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def get_bot_organization_id(db: AsyncSession, bot_id: str) -> str:
    """Helper function to get the organization ID for a bot."""
    from sqlalchemy.future import select
    from app.db.models.bot import Bot
    
    result = await db.execute(select(Bot.organization_id).where(Bot.id == bot_id))
    org_id = result.scalar_one_or_none()
    
    if not org_id:
        raise NotFoundException(f"Bot with ID {bot_id} not found")
        
    return org_id
