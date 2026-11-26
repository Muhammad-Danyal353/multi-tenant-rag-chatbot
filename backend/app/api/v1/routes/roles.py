"""
Role Management Routes

This module contains API endpoints for role management and permissions.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

from app.db.session import get_db, get_async_db
from app.db.models.organization import MemberRole
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException, ForbiddenException

router = APIRouter(prefix="/roles", tags=["Roles"])

# Define permissions for each role
ROLE_PERMISSIONS = {
    "owner": [
        "org:view", "org:edit", "org:delete",
        "bot:create", "bot:view", "bot:edit", "bot:delete",
        "kb:create", "kb:view", "kb:edit", "kb:delete",
        "member:invite", "member:view", "member:edit", "member:remove",
        "billing:view", "billing:edit",
        "analytics:view"
    ],
    "admin": [
        "org:view",
        "bot:create", "bot:view", "bot:edit", "bot:delete",
        "kb:create", "kb:view", "kb:edit", "kb:delete",
        "member:invite", "member:view", "member:edit",
        "analytics:view"
    ],
    "member": [
        "org:view",
        "bot:create", "bot:view", "bot:edit",
        "kb:create", "kb:view", "kb:edit",
        "member:view",
        "analytics:view"
    ],
    "viewer": [
        "org:view",
        "bot:view",
        "kb:view",
        "member:view",
        "analytics:view"
    ]
}

# Define role descriptions
ROLE_DESCRIPTIONS = {
    "owner": "Full access to all features, including billing and organization management.",
    "admin": "Can manage bots, knowledge bases, and team members, but cannot delete the organization or access billing.",
    "member": "Can create and manage bots and knowledge bases, but cannot manage team members.",
    "viewer": "Read-only access to all resources."
}

@router.get(
    "/available",
    summary="Get available roles and their permissions"
)
async def get_available_roles(
    current_user = Depends(get_current_user)
):
    """
    Get all available roles with their permissions and descriptions.
    
    Returns a dictionary with role information:
    - Permissions for each role
    - Description of each role
    - Display name for each role
    """
    roles_info = {}
    
    for role_name in [r.value for r in MemberRole]:
        roles_info[role_name] = {
            "permissions": ROLE_PERMISSIONS.get(role_name, []),
            "description": ROLE_DESCRIPTIONS.get(role_name, ""),
            "display_name": role_name.capitalize()
        }
    
    return {
        "roles": roles_info,
        "permission_categories": [
            {"key": "org", "name": "Organization"},
            {"key": "bot", "name": "Bots"},
            {"key": "kb", "name": "Knowledge Bases"},
            {"key": "member", "name": "Team Members"},
            {"key": "billing", "name": "Billing"},
            {"key": "analytics", "name": "Analytics"}
        ]
    }

@router.get(
    "/permissions",
    summary="Get user permissions for an organization"
)
async def get_user_permissions(
    organization_id: str = Query(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get the current user's permissions for a specific organization.
    
    - **organization_id**: The ID of the organization to check permissions for
    
    Returns the user's role and a list of permissions they have.
    """
    from app.services.organization_service import OrganizationService
    
    try:
        service = OrganizationService(db)
        
        # Get user's role in the organization
        role = await service.get_user_role(
            user_id=current_user.id,
            org_id=organization_id
        )
        
        if not role and not current_user.is_superadmin:
            raise ForbiddenException("You don't have access to this organization")
        
        # Superadmin has all permissions
        if current_user.is_superadmin:
            role_value = "superadmin"
            permissions = list(set([p for perms in ROLE_PERMISSIONS.values() for p in perms]))
            permissions.append("superadmin:*")
        else:
            role_value = role.value
            permissions = ROLE_PERMISSIONS.get(role_value, [])
        
        return {
            "role": role_value,
            "permissions": permissions,
            "is_superadmin": current_user.is_superadmin
        }
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
