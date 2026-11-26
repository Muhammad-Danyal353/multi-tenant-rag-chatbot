"""
Analytics API Routes

This module defines the FastAPI routes for analytics data.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any

from app.db.session import get_db, get_async_db
from app.core.dependencies import get_current_user
from app.db.models.organization import MemberRole
from app.services.analytics_service import AnalyticsService
from app.core.exceptions import NotFoundException, ForbiddenException
from app.schemas.base import ApiResponse
from app.utils.response import create_response

router = APIRouter()


@router.get(
    "/overview/{org_id}",
    response_model=ApiResponse[dict],
    summary="Get organization overview analytics"
)
async def get_organization_overview(
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get overview analytics for an organization.
    
    - **org_id**: Organization ID
    """
    try:
        # Check permissions
        from app.services.organization_service import OrganizationService
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Get analytics
        analytics_service = AnalyticsService(db)
        overview = await analytics_service.get_organization_overview(org_id)
        
        return create_response(
            data=overview,
            message="Organization overview retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/growth/{org_id}",
    response_model=ApiResponse[dict],
    summary="Get organization growth analytics"
)
async def get_organization_growth(
    org_id: str = Path(..., description="Organization ID"),
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get growth analytics for an organization.
    
    - **org_id**: Organization ID
    - **days**: Number of days to look back (default: 30, max: 90)
    """
    try:
        # Check permissions
        from app.services.organization_service import OrganizationService
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Get analytics
        analytics_service = AnalyticsService(db)
        growth = await analytics_service.get_organization_growth(org_id, days)
        
        return create_response(
            data=growth,
            message="Organization growth analytics retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/daily-activity/{org_id}",
    response_model=ApiResponse[dict],
    summary="Get daily activity analytics"
)
async def get_daily_activity(
    org_id: str = Path(..., description="Organization ID"),
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get daily activity analytics for an organization.
    
    - **org_id**: Organization ID
    - **days**: Number of days to look back (default: 30, max: 90)
    """
    try:
        # Check permissions
        from app.services.organization_service import OrganizationService
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Get analytics
        analytics_service = AnalyticsService(db)
        daily_activity = await analytics_service.get_daily_activity(org_id, days)
        
        return create_response(
            data={
                "organization_id": org_id,
                "period_days": days,
                "daily_activity": daily_activity
            },
            message="Daily activity analytics retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/top-bots/{org_id}",
    response_model=ApiResponse[dict],
    summary="Get top performing bots"
)
async def get_top_bots(
    org_id: str = Path(..., description="Organization ID"),
    limit: int = Query(5, ge=1, le=20, description="Number of bots to return"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get top performing bots for an organization.
    
    - **org_id**: Organization ID
    - **limit**: Number of bots to return (default: 5, max: 20)
    """
    try:
        # Check permissions
        from app.services.organization_service import OrganizationService
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Get analytics
        analytics_service = AnalyticsService(db)
        top_bots = await analytics_service.get_top_bots(org_id, limit)
        
        return create_response(
            data={
                "organization_id": org_id,
                "top_bots": top_bots
            },
            message="Top performing bots retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/bot/{bot_id}/performance",
    response_model=ApiResponse[dict],
    summary="Get bot performance analytics"
)
async def get_bot_performance(
    bot_id: str = Path(..., description="Bot ID"),
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get detailed performance analytics for a specific bot.
    
    - **bot_id**: Bot ID
    - **days**: Number of days to look back (default: 30, max: 90)
    """
    try:
        # Get bot to check organization
        from app.db.models.bot import Bot
        bot_query = select(Bot).where(Bot.id == bot_id)
        bot_result = await db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Check permissions
        from app.services.organization_service import OrganizationService
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=bot.organization_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Get analytics
        analytics_service = AnalyticsService(db)
        performance = await analytics_service.get_bot_performance(bot_id, days)
        
        return create_response(
            data=performance,
            message="Bot performance analytics retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/bot/{bot_id}/conversations",
    response_model=ApiResponse[dict],
    summary="Get bot conversation details"
)
async def get_bot_conversations(
    bot_id: str = Path(..., description="Bot ID"),
    limit: int = Query(20, ge=1, le=50, description="Number of conversations to return"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get recent conversation details for a bot.
    
    - **bot_id**: Bot ID
    - **limit**: Number of conversations to return (default: 20, max: 50)
    """
    try:
        # Get bot to check organization
        from app.db.models.bot import Bot
        bot_query = select(Bot).where(Bot.id == bot_id)
        bot_result = await db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Check permissions
        from app.services.organization_service import OrganizationService
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=bot.organization_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Get analytics
        analytics_service = AnalyticsService(db)
        conversations = await analytics_service.get_bot_conversation_details(bot_id, limit)
        
        return create_response(
            data={
                "bot_id": bot_id,
                "bot_name": bot.name,
                "conversations": conversations,
                "total": len(conversations)
            },
            message="Bot conversation details retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/dashboard/{org_id}",
    response_model=ApiResponse[dict],
    summary="Get complete analytics dashboard"
)
async def get_analytics_dashboard(
    org_id: str = Path(..., description="Organization ID"),
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get complete analytics dashboard for an organization.
    
    - **org_id**: Organization ID
    - **days**: Number of days to look back (default: 30, max: 90)
    """
    try:
        # Check permissions
        from app.services.organization_service import OrganizationService
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Get analytics
        analytics_service = AnalyticsService(db)
        
        # Get all analytics data
        overview = await analytics_service.get_organization_overview(org_id)
        growth = await analytics_service.get_organization_growth(org_id, days)
        daily_activity = await analytics_service.get_daily_activity(org_id, days)
        top_bots = await analytics_service.get_top_bots(org_id, 5)
        
        # Combine all data
        return create_response(
            data={
                "overview": overview,
                "growth": growth,
                "daily_activity": daily_activity,
                "top_bots": top_bots
            },
            message="Analytics dashboard retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))