from fastapi import APIRouter, Depends, HTTPException, Path, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db, get_async_db
from app.core.dependencies import get_current_user, require_permission
from app.db.models.user import User
from app.services.domain_allowlist_service import DomainAllowlistService
from app.core.exceptions import NotFoundException, ForbiddenException, ValidationError

router = APIRouter(prefix="/bots", tags=["Domain Allowlist"])

@router.get(
    "/{bot_id}/domains",
    response_model=List[str],
    summary="Get allowed domains for a bot"
)
async def get_allowed_domains(
    bot_id: str = Path(..., description="Bot ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the list of allowed domains for a bot's widget embedding.
    
    - **bot_id**: The ID of the bot
    """
    try:
        # Check if user has permission to view bot settings
        org_id = await get_bot_organization_id(db, bot_id)
        await require_permission("bot:view")(current_user, org_id, db)
        
        service = DomainAllowlistService(db)
        domains = await service.get_allowed_domains(bot_id, org_id)
        
        return domains
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post(
    "/{bot_id}/domains",
    response_model=List[str],
    summary="Add a domain to the allowlist"
)
async def add_domain(
    bot_id: str = Path(..., description="Bot ID"),
    domain: str = Body(..., embed=True, description="Domain to add"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a domain to the bot's allowed domains list.
    
    - **bot_id**: The ID of the bot
    - **domain**: The domain to add (e.g., "example.com" or "*.example.com")
    """
    try:
        # Check if user has permission to update bot settings
        org_id = await get_bot_organization_id(db, bot_id)
        await require_permission("bot:update")(current_user, org_id, db)
        
        service = DomainAllowlistService(db)
        domains = await service.add_domain(bot_id, org_id, domain)
        
        return domains
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete(
    "/{bot_id}/domains/{domain}",
    response_model=List[str],
    summary="Remove a domain from the allowlist"
)
async def remove_domain(
    bot_id: str = Path(..., description="Bot ID"),
    domain: str = Path(..., description="Domain to remove"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove a domain from the bot's allowed domains list.
    
    - **bot_id**: The ID of the bot
    - **domain**: The domain to remove
    """
    try:
        # Check if user has permission to update bot settings
        org_id = await get_bot_organization_id(db, bot_id)
        await require_permission("bot:update")(current_user, org_id, db)
        
        service = DomainAllowlistService(db)
        domains = await service.remove_domain(bot_id, org_id, domain)
        
        return domains
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put(
    "/{bot_id}/domains",
    response_model=List[str],
    summary="Update the entire domain allowlist"
)
async def update_domains(
    bot_id: str = Path(..., description="Bot ID"),
    domains: List[str] = Body(..., description="List of domains"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """
    Replace the entire list of allowed domains for a bot.
    
    - **bot_id**: The ID of the bot
    - **domains**: The new list of allowed domains
    """
    try:
        # Check if user has permission to update bot settings
        org_id = await get_bot_organization_id(db, bot_id)
        await require_permission("bot:update")(current_user, org_id, db)
        
        service = DomainAllowlistService(db)
        updated_domains = await service.update_domains(bot_id, org_id, domains)
        
        return updated_domains
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
