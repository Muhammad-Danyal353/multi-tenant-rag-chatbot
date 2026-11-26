"""
Admin Routes

Handles admin and super admin operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.db.session import get_db, get_async_db
from app.db.models.organization import Organization, SubscriptionStatus
from app.db.models.user import User
from app.schemas.organization import OrganizationResponse, OrganizationListResponse
from app.core.dependencies import get_current_user, require_super_admin
from app.core.exceptions import NotFoundException, ForbiddenException
from app.schemas.base import ApiResponse
from app.utils.response import create_response

router = APIRouter()


@router.get(
    "/organizations", 
    response_model=ApiResponse[OrganizationListResponse],
    summary="List all organizations"
)
async def list_organizations(
    search: Optional[str] = Query(None, description="Search by name or ID"),
    status: Optional[str] = Query(None, description="Filter by subscription status"),
    plan: Optional[str] = Query(None, description="Filter by subscription plan"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    List all organizations (super admin only).
    
    - **search**: Optional search by name or ID
    - **status**: Optional filter by subscription status
    - **plan**: Optional filter by subscription plan
    - **is_active**: Optional filter by active status
    - **sort_by**: Field to sort by (created_at, name, subscription_plan, etc.)
    - **sort_order**: Sort order (asc or desc)
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (pagination)
    """
    from app.services.admin_service import AdminService
    
    admin_service = AdminService(db)
    orgs, total = await admin_service.list_organizations(
        search=search,
        status=status,
        plan=plan,
        is_active=is_active,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit
    )
    
    return create_response(
        data={
            "items": orgs,
            "total": total
        },
        message="Organizations retrieved successfully"
    )


@router.get(
    "/organizations/{org_id}", 
    response_model=ApiResponse[dict],
    summary="Get organization details"
)
async def get_organization(
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Get details of a specific organization (super admin only).
    
    - **org_id**: Organization ID
    """
    from app.services.admin_service import AdminService
    
    try:
        admin_service = AdminService(db)
        org_details = await admin_service.get_organization_details(org_id)
        return create_response(
            data=org_details,
            message="Organization details retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put(
    "/organizations/{org_id}/toggle-active",
    response_model=ApiResponse[dict],
    summary="Toggle organization active status"
)
async def toggle_organization_active(
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Toggle active status for an organization (super admin only).
    
    - **org_id**: Organization ID
    """
    from app.services.admin_service import AdminService
    
    try:
        admin_service = AdminService(db)
        result = await admin_service.toggle_organization_active(org_id)
        
        status_message = "activated" if result["is_active"] else "suspended"
        
        return create_response(
            data={
                "message": f"Organization {result['name']} has been {status_message}",
                "organization_id": org_id,
                "is_active": result["is_active"]
            },
            message="Organization status updated successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/users",
    response_model=ApiResponse[dict],
    summary="List all users"
)
async def list_users(
    search: Optional[str] = Query(None, description="Search by name or email"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verified status"),
    is_superadmin: Optional[bool] = Query(None, description="Filter by superadmin status"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    List all users (super admin only).
    
    - **search**: Optional search by name or email
    - **is_active**: Optional filter by active status
    - **is_verified**: Optional filter by verified status
    - **is_superadmin**: Optional filter by superadmin status
    - **sort_by**: Field to sort by (created_at, full_name, email, etc.)
    - **sort_order**: Sort order (asc or desc)
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (pagination)
    """
    from app.services.admin_service import AdminService
    
    admin_service = AdminService(db)
    users, total = await admin_service.list_users(
        search=search,
        is_active=is_active,
        is_verified=is_verified,
        is_superadmin=is_superadmin,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit
    )
    
    return create_response(
        data={
            "items": users,
            "total": total
        },
        message="Users retrieved successfully"
    )


@router.get(
    "/users/{user_id}",
    response_model=ApiResponse[dict],
    summary="Get user details"
)
async def get_user(
    user_id: str = Path(..., description="User ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Get details of a specific user (super admin only).
    
    - **user_id**: User ID
    """
    from app.services.admin_service import AdminService
    
    try:
        admin_service = AdminService(db)
        user_details = await admin_service.get_user_details(user_id)
        return create_response(
            data=user_details,
            message="User details retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put(
    "/users/{user_id}/toggle-superadmin",
    response_model=ApiResponse[dict],
    summary="Toggle superadmin status"
)
async def toggle_superadmin(
    user_id: str = Path(..., description="User ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Toggle superadmin status for a user (super admin only).
    
    - **user_id**: User ID
    """
    from app.services.admin_service import AdminService
    
    try:
        admin_service = AdminService(db)
        result = await admin_service.toggle_user_superadmin(user_id)
        
        return create_response(
            data={
                "message": f"User {result['full_name']} superadmin status set to {result['is_superadmin']}",
                "user_id": user_id,
                "is_superadmin": result["is_superadmin"]
            },
            message="User superadmin status updated successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put(
    "/users/{user_id}/toggle-active",
    response_model=ApiResponse[dict],
    summary="Toggle user active status"
)
async def toggle_user_active(
    user_id: str = Path(..., description="User ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Toggle active status for a user (super admin only).
    
    - **user_id**: User ID
    """
    from app.services.admin_service import AdminService
    
    try:
        admin_service = AdminService(db)
        result = await admin_service.toggle_user_active(user_id)
        
        return create_response(
            data={
                "message": f"User {result['full_name']} active status set to {result['is_active']}",
                "user_id": user_id,
                "is_active": result["is_active"]
            },
            message="User active status updated successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/stats",
    response_model=ApiResponse[dict],
    summary="Get platform-wide statistics"
)
async def get_platform_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Get platform-wide statistics (super admin only).
    """
    from app.services.stats_service import StatsService
    
    stats_service = StatsService(db)
    
    # Get platform overview statistics
    overview = await stats_service.get_platform_overview()
    
    # Get growth statistics for the last 30 days
    growth = await stats_service.get_growth_stats(days=30)
    
    # Get subscription statistics
    subscriptions = await stats_service.get_subscription_stats()
    
    return create_response(
        data={
            **overview,
            "growth": growth,
            "subscriptions": subscriptions
        },
        message="Platform statistics retrieved successfully"
    )


@router.get(
    "/stats/daily-activity",
    response_model=ApiResponse[dict],
    summary="Get daily activity statistics"
)
async def get_daily_activity_stats(
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Get daily activity statistics (super admin only).
    
    - **days**: Number of days to look back (default: 30, max: 90)
    """
    from app.services.stats_service import StatsService
    
    stats_service = StatsService(db)
    daily_activity = await stats_service.get_daily_activity(days=days)
    
    return create_response(
        data={
            "daily_activity": daily_activity,
            "period_days": days
        },
        message="Daily activity statistics retrieved successfully"
    )


@router.get(
    "/stats/top-organizations",
    response_model=ApiResponse[dict],
    summary="Get top organizations by usage"
)
async def get_top_organizations(
    limit: int = Query(10, ge=1, le=50, description="Number of organizations to return"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Get top organizations by message count (super admin only).
    
    - **limit**: Number of organizations to return (default: 10, max: 50)
    """
    from app.services.stats_service import StatsService
    
    stats_service = StatsService(db)
    top_orgs = await stats_service.get_top_organizations(limit=limit)
    
    return create_response(
        data={
            "top_organizations": top_orgs,
            "limit": limit
        },
        message="Top organizations retrieved successfully"
    )


@router.get(
    "/audit-logs",
    response_model=ApiResponse[dict],
    summary="Get global audit logs"
)
async def get_global_audit_logs(
    organization_id: Optional[str] = Query(None, description="Filter by organization ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Get global audit logs (super admin only).
    
    - **organization_id**: Optional filter by organization ID
    - **user_id**: Optional filter by user ID
    - **resource_type**: Optional filter by resource type
    - **action**: Optional filter by action
    - **start_date**: Optional start date filter (ISO format)
    - **end_date**: Optional end date filter (ISO format)
    - **page**: Page number for pagination
    - **page_size**: Page size for pagination
    """
    from app.services.audit_service import AuditService
    
    # Create audit service
    audit_service = AuditService(db)
    
    # Get audit logs
    logs = await audit_service.get_audit_logs(
        organization_id=organization_id,
        user_id=user_id,
        resource_type=resource_type,
        action=action,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
        db=db
    )
    
    return create_response(
        data=logs,
        message="Audit logs retrieved successfully"
    )