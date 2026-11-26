"""
Audit API Routes

This module defines the FastAPI routes for audit logs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any

from app.db.session import get_db, get_async_db
from app.core.dependencies import get_current_user, require_permission
from app.schemas.auth import UserResponse
from app.services.audit_service import get_audit_service, AuditService

router = APIRouter()


@router.get(
    "/{organization_id}",
    summary="Get audit logs for an organization"
)
async def get_audit_logs(
    organization_id: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get audit logs for an organization with filtering and pagination.
    
    Requires admin or owner permissions.
    """
    # Check permissions (only admins and owners can view audit logs)
    require_permission(current_user, "audit:view", organization_id=organization_id)
    
    # Get audit logs
    logs = await audit_service.get_audit_logs(
        organization_id=organization_id,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
        db=db
    )
    
    return logs


@router.get(
    "/{organization_id}/users/{user_id}/activity",
    summary="Get activity history for a user"
)
async def get_user_activity(
    organization_id: str,
    user_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get recent activity history for a specific user.
    
    Requires admin or owner permissions.
    """
    # Check permissions (only admins and owners can view user activity)
    require_permission(current_user, "audit:view", organization_id=organization_id)
    
    # Get user activity
    activity = await audit_service.get_user_activity(
        organization_id=organization_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        db=db
    )
    
    return {"items": activity, "total": len(activity)}


@router.get(
    "/{organization_id}/resources/{resource_type}/{resource_id}/history",
    summary="Get change history for a resource"
)
async def get_resource_history(
    organization_id: str,
    resource_type: str,
    resource_id: str,
    current_user: UserResponse = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get change history for a specific resource.
    
    Requires view permissions for the resource type.
    """
    # Check permissions
    require_permission(current_user, f"{resource_type}:view", organization_id=organization_id)
    
    # Get resource history
    history = await audit_service.get_resource_history(
        organization_id=organization_id,
        resource_type=resource_type,
        resource_id=resource_id,
        db=db
    )
    
    return {"items": history, "total": len(history)}
