"""
Invitation Routes

This module contains API endpoints for managing organization invitations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_db, get_async_db
from app.schemas.organization import (
    InvitationCreate,
    InvitationResponse,
    InvitationListResponse,
    InvitationAccept
)
from app.db.models.organization import MemberRole
from app.services.invitation_service import InvitationService
from app.services.organization_service import OrganizationService
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException

router = APIRouter(prefix="/invitations", tags=["Invitations"])

@router.post(
    "/accept",
    status_code=status.HTTP_200_OK,
    summary="Accept an invitation to join an organization"
)
async def accept_invitation(
    data: InvitationAccept,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Accept an invitation to join an organization.
    
    - **token**: Invitation token received in the email
    """
    try:
        service = InvitationService(db)
        result = await service.accept_invitation(
            token=data.token,
            user_id=current_user.id
        )
        return result
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/validate/{token}",
    status_code=status.HTTP_200_OK,
    summary="Validate an invitation token"
)
async def validate_invitation(
    token: str = Path(..., description="Invitation token"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Validate an invitation token without accepting it.
    
    - **token**: Invitation token to validate
    """
    try:
        service = InvitationService(db)
        invitation, organization = await service.get_invitation_by_token(token)
        
        return {
            "valid": True,
            "organization_name": organization.name,
            "email": invitation.email,
            "role": invitation.role.value,
            "expires_at": invitation.expires_at
        }
    except NotFoundException:
        return {"valid": False, "reason": "Invitation not found"}
    except ForbiddenException as e:
        return {"valid": False, "reason": str(e)}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/organization/{org_id}",
    response_model=InvitationListResponse,
    summary="List pending invitations for an organization"
)
async def list_invitations(
    org_id: str = Path(..., description="Organization ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    List all pending invitations for an organization.
    
    - **org_id**: Organization ID
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (pagination)
    """
    try:
        # Check if user has permission
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Get invitations
        invitation_service = InvitationService(db)
        invitations, total = await invitation_service.list_invitations(
            organization_id=org_id,
            skip=skip,
            limit=limit
        )
        
        return {
            "items": invitations,
            "total": total
        }
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete(
    "/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an invitation"
)
async def delete_invitation(
    invitation_id: str = Path(..., description="Invitation ID"),
    org_id: str = Query(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Delete an invitation.
    
    - **invitation_id**: Invitation ID
    - **org_id**: Organization ID
    """
    try:
        # Check if user has permission
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Delete invitation
        invitation_service = InvitationService(db)
        await invitation_service.delete_invitation(
            organization_id=org_id,
            invitation_id=invitation_id,
            user_id=current_user.id
        )
        
        return None
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post(
    "/{invitation_id}/resend",
    status_code=status.HTTP_200_OK,
    summary="Resend an invitation email"
)
async def resend_invitation(
    invitation_id: str = Path(..., description="Invitation ID"),
    org_id: str = Query(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Resend an invitation email.
    
    - **invitation_id**: Invitation ID
    - **org_id**: Organization ID
    """
    try:
        # Check if user has permission
        org_service = OrganizationService(db)
        await org_service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Resend invitation
        invitation_service = InvitationService(db)
        invitation = await invitation_service.resend_invitation(
            organization_id=org_id,
            invitation_id=invitation_id,
            user_id=current_user.id
        )
        
        return {
            "message": f"Invitation resent to {invitation.email}",
            "expires_at": invitation.expires_at
        }
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
