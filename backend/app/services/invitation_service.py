"""
Invitation Service

This module provides services for managing organization invitations.
"""

from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import joinedload
from typing import List, Optional, Dict, Any, Tuple
import uuid
import secrets
from datetime import datetime, timedelta

from app.db.session import get_db, get_async_db
from app.db.models.organization import Organization, Membership, MemberRole
from app.db.models.invitation import Invitation
from app.db.models.user import User
from app.services.email_service import EmailService
from app.services.audit_service import AuditService
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException


class InvitationService:
    """Service for managing organization invitations"""
    
    def __init__(self, db: AsyncSession = Depends(get_async_db)):
        self.db = db
        self.email_service = EmailService()
        self.audit_service = AuditService(db)
    
    async def create_invitation(
        self,
        organization_id: str,
        inviter_id: str,
        email: str,
        role: MemberRole
    ) -> Invitation:
        """
        Create a new invitation to join an organization.
        
        Args:
            organization_id: Organization ID
            inviter_id: ID of user sending the invitation
            email: Email of the user to invite
            role: Role to assign to the new member
            
        Returns:
            Created invitation
            
        Raises:
            NotFoundException: If organization not found
            ConflictException: If user is already a member or invited
        """
        # Check if organization exists
        org_query = select(Organization).where(Organization.id == organization_id)
        org_result = await self.db.execute(org_query)
        organization = org_result.scalar_one_or_none()
        
        if not organization:
            raise NotFoundException(f"Organization with ID {organization_id} not found")
        
        # Check if user already exists
        user_query = select(User).where(User.email == email)
        user_result = await self.db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        # If user exists, check if already a member
        if user:
            membership_query = (
                select(Membership)
                .where(
                    and_(
                        Membership.user_id == user.id,
                        Membership.organization_id == organization_id
                    )
                )
            )
            
            membership_result = await self.db.execute(membership_query)
            existing_membership = membership_result.scalar_one_or_none()
            
            if existing_membership:
                raise ConflictException(f"User {email} is already a member of this organization")
        
        # Check if invitation already exists
        invitation_query = (
            select(Invitation)
            .where(
                and_(
                    Invitation.email == email,
                    Invitation.organization_id == organization_id,
                    Invitation.accepted_at.is_(None)
                )
            )
        )
        
        invitation_result = await self.db.execute(invitation_query)
        existing_invitation = invitation_result.scalar_one_or_none()
        
        if existing_invitation:
            raise ConflictException(f"User {email} has already been invited to this organization")
        
        # Get inviter details
        inviter_query = select(User).where(User.id == inviter_id)
        inviter_result = await self.db.execute(inviter_query)
        inviter = inviter_result.scalar_one_or_none()
        
        if not inviter:
            raise NotFoundException("Inviter not found")
        
        # Create invitation token
        token = secrets.token_urlsafe(32)
        
        # Create invitation
        invitation = Invitation(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            invited_by=inviter_id,
            email=email,
            role=role,
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        self.db.add(invitation)
        await self.db.commit()
        
        # Send invitation email
        await self.email_service.send_organization_invitation(
            to_email=email,
            inviter_name=inviter.full_name,
            organization_name=organization.name,
            invitation_token=token,
            role=role.value
        )
        
        # Log the action
        await self.audit_service.log_action(
            user_id=inviter_id,
            organization_id=organization_id,
            action="create",
            resource_type="invitation",
            resource_id=invitation.id,
            changes={
                "email": email,
                "role": role.value
            }
        )
        
        return invitation
    
    async def get_invitation_by_token(self, token: str) -> Tuple[Invitation, Organization]:
        """
        Get invitation by token.
        
        Args:
            token: Invitation token
            
        Returns:
            Tuple of (invitation, organization)
            
        Raises:
            NotFoundException: If invitation not found
            ForbiddenException: If invitation expired or already accepted
        """
        # Get invitation with organization
        query = (
            select(Invitation, Organization)
            .join(Organization, Invitation.organization_id == Organization.id)
            .where(Invitation.token == token)
        )
        
        result = await self.db.execute(query)
        invitation_with_org = result.one_or_none()
        
        if not invitation_with_org:
            raise NotFoundException("Invitation not found")
            
        invitation, organization = invitation_with_org
        
        # Check if expired
        if invitation.is_expired():
            raise ForbiddenException("Invitation has expired")
            
        # Check if already accepted
        if invitation.is_accepted():
            raise ForbiddenException("Invitation has already been accepted")
            
        return invitation, organization
    
    async def accept_invitation(
        self,
        token: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Accept an invitation to join an organization.
        
        Args:
            token: Invitation token
            user_id: User ID accepting the invitation
            
        Returns:
            Dictionary with membership details
            
        Raises:
            NotFoundException: If invitation not found
            ForbiddenException: If invitation expired or already accepted
            ConflictException: If user is already a member
        """
        # Get invitation and organization
        invitation, organization = await self.get_invitation_by_token(token)
        
        # Get user
        user_query = select(User).where(User.id == user_id)
        user_result = await self.db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise NotFoundException("User not found")
            
        # Check if user's email matches invitation
        if user.email.lower() != invitation.email.lower():
            raise ForbiddenException("This invitation was sent to a different email address")
            
        # Check if already a member
        membership_query = (
            select(Membership)
            .where(
                and_(
                    Membership.user_id == user_id,
                    Membership.organization_id == invitation.organization_id
                )
            )
        )
        
        membership_result = await self.db.execute(membership_query)
        existing_membership = membership_result.scalar_one_or_none()
        
        if existing_membership:
            raise ConflictException("You are already a member of this organization")
            
        # Create membership
        membership = Membership(
            id=str(uuid.uuid4()),
            user_id=user_id,
            organization_id=invitation.organization_id,
            role=invitation.role,
            invited_by=invitation.invited_by
        )
        
        # Mark invitation as accepted
        invitation.accepted_at = datetime.utcnow()
        
        self.db.add(membership)
        await self.db.commit()
        
        # Log the action
        await self.audit_service.log_action(
            user_id=user_id,
            organization_id=invitation.organization_id,
            action="accept",
            resource_type="invitation",
            resource_id=invitation.id
        )
        
        # Return membership details
        return {
            "id": membership.id,
            "user_id": user_id,
            "organization_id": invitation.organization_id,
            "organization_name": organization.name,
            "role": invitation.role.value,
            "invited_by": invitation.invited_by
        }
    
    async def list_invitations(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Dict], int]:
        """
        List pending invitations for an organization.
        
        Args:
            organization_id: Organization ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (list of invitations, total count)
        """
        # Get organization
        org_query = select(Organization).where(Organization.id == organization_id)
        org_result = await self.db.execute(org_query)
        organization = org_result.scalar_one_or_none()
        
        if not organization:
            raise NotFoundException(f"Organization with ID {organization_id} not found")
            
        # Get pending invitations
        query = (
            select(Invitation)
            .where(
                and_(
                    Invitation.organization_id == organization_id,
                    Invitation.accepted_at.is_(None)
                )
            )
            .order_by(Invitation.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        invitations =  result.scalars().all()
        
        # Get total count
        count_query = (
            select(func.count())
            .select_from(Invitation)
            .where(
                and_(
                    Invitation.organization_id == organization_id,
                    Invitation.accepted_at.is_(None)
                )
            )
        )
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()
        
        # Get inviter details
        inviter_ids = {inv.invited_by for inv in invitations if inv.invited_by}
        inviters = {}
        
        if inviter_ids:
            inviter_query = select(User).where(User.id.in_(inviter_ids))
            inviter_result = await self.db.execute(inviter_query)
            inviters = {user.id: user for user in inviter_result.scalars().all()}
        
        # Format response
        invitation_list = []
        for inv in invitations:
            inviter = inviters.get(inv.invited_by)
            invitation_list.append({
                "id": inv.id,
                "email": inv.email,
                "organization_id": inv.organization_id,
                "organization_name": organization.name,
                "role": inv.role.value,
                "invited_by": inv.invited_by,
                "inviter_name": inviter.full_name if inviter else None,
                "created_at": inv.created_at,
                "expires_at": inv.expires_at,
                "is_expired": inv.is_expired(),
                "is_accepted": inv.is_accepted()
            })
        
        return invitation_list, total
    
    async def delete_invitation(
        self,
        organization_id: str,
        invitation_id: str,
        user_id: str
    ) -> bool:
        """
        Delete an invitation.
        
        Args:
            organization_id: Organization ID
            invitation_id: Invitation ID
            user_id: User ID performing the deletion
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundException: If invitation not found
        """
        # Get invitation
        query = (
            select(Invitation)
            .where(
                and_(
                    Invitation.id == invitation_id,
                    Invitation.organization_id == organization_id
                )
            )
        )
        
        result = await self.db.execute(query)
        invitation = result.scalar_one_or_none()
        
        if not invitation:
            raise NotFoundException(f"Invitation with ID {invitation_id} not found")
            
        # Delete invitation
        await self.db.delete(invitation)
        await self.db.commit()
        
        # Log the action
        await self.audit_service.log_action(
            user_id=user_id,
            organization_id=organization_id,
            action="delete",
            resource_type="invitation",
            resource_id=invitation_id
        )
        
        return True
    
    async def resend_invitation(
        self,
        organization_id: str,
        invitation_id: str,
        user_id: str
    ) -> Invitation:
        """
        Resend an invitation email.
        
        Args:
            organization_id: Organization ID
            invitation_id: Invitation ID
            user_id: User ID resending the invitation
            
        Returns:
            Updated invitation
            
        Raises:
            NotFoundException: If invitation not found
            ForbiddenException: If invitation already accepted
        """
        # Get invitation with organization
        query = (
            select(Invitation, Organization)
            .join(Organization, Invitation.organization_id == Organization.id)
            .where(
                and_(
                    Invitation.id == invitation_id,
                    Invitation.organization_id == organization_id
                )
            )
        )
        
        result = await self.db.execute(query)
        invitation_with_org = result.one_or_none()
        
        if not invitation_with_org:
            raise NotFoundException(f"Invitation with ID {invitation_id} not found")
            
        invitation, organization = invitation_with_org
        
        # Check if already accepted
        if invitation.is_accepted():
            raise ForbiddenException("Invitation has already been accepted")
            
        # Get inviter details
        inviter_query = select(User).where(User.id == user_id)
        inviter_result = await self.db.execute(inviter_query)
        inviter = inviter_result.scalar_one_or_none()
        
        if not inviter:
            raise NotFoundException("Inviter not found")
            
        # Update expiration
        invitation.expires_at = datetime.utcnow() + timedelta(days=7)
        await self.db.commit()
        
        # Resend invitation email
        await self.email_service.send_organization_invitation(
            to_email=invitation.email,
            inviter_name=inviter.full_name,
            organization_name=organization.name,
            invitation_token=invitation.token,
            role=invitation.role.value
        )
        
        # Log the action
        await self.audit_service.log_action(
            user_id=user_id,
            organization_id=organization_id,
            action="resend",
            resource_type="invitation",
            resource_id=invitation_id
        )
        
        return invitation
