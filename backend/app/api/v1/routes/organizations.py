"""
Organization Routes

This module contains API endpoints for organization management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_db, get_async_db
from app.schemas.organization import (
    MemberRoleEnum,
    OrganizationCreate, 
    OrganizationUpdate, 
    OrganizationResponse, 
    OrganizationListResponse,
    MemberCreate,
    MemberUpdate,
    MemberResponse,
    MemberListResponse,
    InvitationCreate,
    InvitationResponse
)
from app.schemas.base import ApiResponse
from app.db.models.organization import MemberRole
from app.services.organization_service import OrganizationService
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException
from app.utils.response import create_response

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.post(
    "", 
    response_model=ApiResponse[OrganizationResponse], 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization"
)
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new organization with the current user as owner.
    
    - **name**: Organization name
    - **slug**: Optional URL-friendly slug (generated from name if not provided)
    """
    try:
        service = OrganizationService(db)
        org = await service.create_organization(
            user_id=current_user.id,
            name=data.name,
            slug=data.slug
        )
        return create_response(
            data=org,
            message="Organization created successfully",
            status_code=201
        )
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "", 
    response_model=ApiResponse[OrganizationListResponse],
    summary="List user's organizations"
)
async def list_organizations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    List all organizations that the current user is a member of.
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (pagination)
    """
    service = OrganizationService(db)
    orgs, total = await service.list_organizations(
        user_id=current_user.id,
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
    "/me", 
    response_model=ApiResponse[dict],
    summary="Get current user's organization"
)
async def get_my_organization(
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get the current user's primary organization.
    
    Returns the organization that the user is a member of.
    If the user is a member of multiple organizations, returns the first one.
    """
    try:
        service = OrganizationService(db)
        
        # Get user's organizations
        orgs, total = await service.list_organizations(
            user_id=current_user.id,
            skip=0,
            limit=1
        )
        
        if total == 0:
            raise NotFoundException("You are not a member of any organization")
        
        # Return the first organization (orgs is already a list of dicts)
        organization = orgs[0]
        
        return create_response(
            data={"organization": organization},
            message="Organization retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/{org_id}", 
    response_model=ApiResponse[OrganizationResponse],
    summary="Get organization details"
)
async def get_organization(
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get details of a specific organization.
    
    - **org_id**: Organization ID
    """
    try:
        service = OrganizationService(db)
        
        # Check if user is a member
        has_access = await service.check_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        if not has_access and not current_user.is_superadmin:
            raise ForbiddenException("You don't have access to this organization")
        
        org = await service.get_organization(org_id)
        return create_response(
            data=org,
            message="Organization retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put(
    "/{org_id}", 
    response_model=ApiResponse[OrganizationResponse],
    summary="Update organization details"
)
async def update_organization(
    data: OrganizationUpdate,
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Update organization details.
    
    - **org_id**: Organization ID
    - **name**: New organization name (optional)
    - **settings**: Organization settings (optional)
    - **is_active**: Organization active status (optional)
    """
    try:
        service = OrganizationService(db)
        
        # Check if user has permission
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Update organization
        org = await service.update_organization(
            org_id=org_id,
            user_id=current_user.id,
            data=data.dict(exclude_unset=True)
        )
        
        return create_response(
            data=org,
            message="Organization updated successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete(
    "/{org_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete organization"
)
async def delete_organization(
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Delete (soft delete) an organization.
    
    - **org_id**: Organization ID
    """
    try:
        service = OrganizationService(db)
        
        # Check if user has permission
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER]
        )
        
        # Delete organization
        await service.delete_organization(
            org_id=org_id,
            user_id=current_user.id
        )
        
        return None
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# Member management endpoints
@router.get(
    "/{org_id}/members", 
    response_model=ApiResponse[MemberListResponse],
    summary="List organization members"
)
async def list_members(
    org_id: str = Path(..., description="Organization ID"),
    search: Optional[str] = Query(None, description="Search term for email or name"),
    role: Optional[MemberRoleEnum] = Query(None, description="Filter by role"),
    sort_by: str = Query("created_at", description="Field to sort by (created_at, full_name, email, role)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    List all members of an organization with search and filters.
    
    - **org_id**: Organization ID
    - **search**: Optional search term for email or name
    - **role**: Optional filter by role
    - **sort_by**: Field to sort by (created_at, full_name, email, role)
    - **sort_order**: Sort order (asc or desc)
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (pagination)
    """
    try:
        service = OrganizationService(db)
        
        # Check if user has permission
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Convert role enum if provided
        db_role = None
        if role:
            db_role = MemberRole(role.value)
        
        # Get members
        members, total = await service.list_members(
            org_id=org_id,
            search=search,
            role=db_role,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=limit
        )
        
        return create_response(
            data={
                "items": members,
                "total": total
            },
            message="Members retrieved successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post(
    "/{org_id}/invite", 
    response_model=ApiResponse[InvitationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Invite a member to the organization"
)
async def invite_member(
    invitation: InvitationCreate,
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Invite a user to join the organization.
    
    - **org_id**: Organization ID
    - **email**: Email of the user to invite
    - **role**: Role to assign to the new member
    """
    try:
        service = OrganizationService(db)
        
        # Check if user has permission
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Invite member
        result = await service.invite_member(
            org_id=org_id,
            inviter_id=current_user.id,
            email=invitation.email,
            role=invitation.role
        )
        
        return create_response(
            data=result,
            message="Member invited successfully",
            status_code=201
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put(
    "/{org_id}/members/{member_id}/role", 
    response_model=ApiResponse[MemberResponse],
    summary="Update member role"
)
async def update_member_role(
    role_update: MemberUpdate,
    org_id: str = Path(..., description="Organization ID"),
    member_id: str = Path(..., description="Membership ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Update a member's role in the organization.
    
    - **org_id**: Organization ID
    - **member_id**: Membership ID
    - **role**: New role to assign
    """
    try:
        service = OrganizationService(db)
        
        # Check if user has permission
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Update role
        result = await service.update_member_role(
            org_id=org_id,
            user_id=current_user.id,
            member_id=member_id,
            new_role=role_update.role
        )
        
        return create_response(
            data=result,
            message="Member role updated successfully"
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete(
    "/{org_id}/members/{user_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from organization"
)
async def remove_member(
    org_id: str = Path(..., description="Organization ID"),
    user_id: str = Path(..., description="User ID of the member to remove"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Remove a member from the organization.
    
    - **org_id**: Organization ID
    - **user_id**: User ID of the member to remove
    """
    try:
        service = OrganizationService(db)
        
        # Check if user has permission
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Remove member
        await service.remove_member(
            org_id=org_id,
            user_id=current_user.id,
            member_user_id=user_id
        )
        
        return None
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
