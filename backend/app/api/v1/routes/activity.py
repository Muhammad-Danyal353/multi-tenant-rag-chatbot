"""
Activity Tracking Routes

This module contains API endpoints for tracking user activity.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.db.session import get_db, get_async_db
from app.db.models.organization import MemberRole
from app.services.organization_service import OrganizationService
from app.services.audit_service import AuditService
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException, ForbiddenException

router = APIRouter(prefix="/activity", tags=["Activity"])

@router.get(
    "/organization/{org_id}/members/{user_id}",
    summary="Get activity for a specific member"
)
async def get_member_activity(
    org_id: str = Path(..., description="Organization ID"),
    user_id: str = Path(..., description="User ID"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of activities to return"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get recent activity for a specific team member.
    
    - **org_id**: Organization ID
    - **user_id**: User ID of the member
    - **start_date**: Optional start date filter (ISO format)
    - **end_date**: Optional end date filter (ISO format)
    - **limit**: Maximum number of activities to return
    """
    try:
        # Check if user has permission
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Check if the target user is a member of the organization
        is_member = await org_service.check_permission(
            user_id=user_id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        if not is_member:
            raise NotFoundException(f"User {user_id} is not a member of this organization")
        
        # Get user activity
        audit_service = AuditService(db)
        activities = await audit_service.get_user_activity(
            organization_id=org_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            db=db
        )
        
        return {
            "user_id": user_id,
            "organization_id": org_id,
            "activities": activities
        }
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/organization/{org_id}/recent",
    summary="Get recent activity for the organization"
)
async def get_organization_activity(
    org_id: str = Path(..., description="Organization ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    days: int = Query(7, ge=1, le=30, description="Number of days to look back"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get recent activity for the entire organization.
    
    - **org_id**: Organization ID
    - **resource_type**: Optional filter by resource type (e.g., "bot", "knowledge_base")
    - **action**: Optional filter by action (e.g., "create", "update", "delete")
    - **days**: Number of days to look back
    - **page**: Page number for pagination
    - **page_size**: Page size for pagination
    """
    try:
        # Check if user has permission
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Calculate start date
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        # Get audit logs
        audit_service = AuditService(db)
        logs = await audit_service.get_audit_logs(
            organization_id=org_id,
            resource_type=resource_type,
            action=action,
            start_date=start_date,
            page=page,
            page_size=page_size,
            db=db
        )
        
        return logs
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
