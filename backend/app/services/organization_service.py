"""
Organization Service

This module provides services for managing organizations, members, and invitations.
"""

from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import joinedload
from typing import List, Optional, Dict, Any, Tuple
import uuid
from datetime import datetime, timedelta

from app.db.session import get_db, get_async_db
from app.db.models.organization import Organization, Membership, MemberRole, SubscriptionPlan, SubscriptionStatus
from app.db.models.user import User
from app.services.email_service import EmailService
from app.services.audit_service import AuditService
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException

class OrganizationService:
    """Service for managing organizations and their members"""
    
    def __init__(self, db: AsyncSession = Depends(get_async_db)):
        self.db = db
        self.email_service = EmailService()
        self.audit_service = AuditService(db)
    
    async def create_organization(self, user_id: str, name: str, slug: Optional[str] = None) -> Organization:
        """
        Create a new organization with the current user as owner.
        
        Args:
            user_id: ID of the user creating the organization
            name: Name of the organization
            slug: URL-friendly slug (optional, generated from name if not provided)
            
        Returns:
            The created organization
        """
        # Generate slug from name if not provided
        if not slug:
            import re
            slug = re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-'))
        
        # Check if slug is already taken
        existing_org = await self.db.execute(select(Organization).where(Organization.slug == slug))
        if existing_org.scalar_one_or_none():
            raise ConflictException(f"Organization with slug '{slug}' already exists")
        
        # Create organization with default settings
        new_org = Organization(
            id=str(uuid.uuid4()),
            name=name,
            slug=slug,
            subscription_plan=SubscriptionPlan.FREE,
            subscription_status=SubscriptionStatus.ACTIVE,
            usage_limits={
                "messages": 100,
                "storage_mb": 100,
                "bots": 1
            },
            settings={},
            is_active=True
        )
        
        self.db.add(new_org)
        await self.db.flush()
        
        # Add the creator as owner
        membership = Membership(
            id=str(uuid.uuid4()),
            user_id=user_id,
            organization_id=new_org.id,
            role=MemberRole.OWNER
        )
        
        self.db.add(membership)
        await self.db.commit()
        
        # Log the action
        await self.audit_service.log_action(
            user_id=user_id,
            organization_id=new_org.id,
            action="create",
            resource_type="organization",
            resource_id=new_org.id,
            changes={"name": name, "slug": slug}
        )
        
        return new_org
    
    async def get_organization(self, org_id: str) -> Organization:
        """
        Get organization by ID
        
        Args:
            org_id: Organization ID
            
        Returns:
            Organization object
            
        Raises:
            NotFoundException: If organization not found
        """
        result = await self.db.execute(
            select(Organization)
            .where(and_(Organization.id == org_id, Organization.is_active == True))
        )
        
        org = result.scalar_one_or_none()
        if not org:
            raise NotFoundException(f"Organization with ID {org_id} not found")
            
        return org
    
    async def update_organization(
        self, 
        org_id: str, 
        user_id: str, 
        data: Dict[str, Any]
    ) -> Organization:
        """
        Update organization details
        
        Args:
            org_id: Organization ID
            user_id: ID of user making the update
            data: Dictionary with fields to update
            
        Returns:
            Updated organization
            
        Raises:
            NotFoundException: If organization not found
        """
        org = await self.get_organization(org_id)
        
        # Track changes for audit log
        changes = {}
        
        # Update fields
        if "name" in data and data["name"] != org.name:
            changes["name"] = {"old": org.name, "new": data["name"]}
            org.name = data["name"]
            
        if "settings" in data and data["settings"] != org.settings:
            changes["settings"] = {"old": org.settings, "new": data["settings"]}
            org.settings = data["settings"]
            
        if "is_active" in data and data["is_active"] != org.is_active:
            changes["is_active"] = {"old": org.is_active, "new": data["is_active"]}
            org.is_active = data["is_active"]
        
        # Only update if there were changes
        if changes:
            org.updated_at = datetime.utcnow()
            await self.db.commit()
            
            # Log the action
            await self.audit_service.log_action(
                user_id=user_id,
                organization_id=org_id,
                action="update",
                resource_type="organization",
                resource_id=org_id,
                changes=changes
            )
        
        return org
    
    async def delete_organization(self, org_id: str, user_id: str) -> bool:
        """
        Soft delete an organization
        
        Args:
            org_id: Organization ID
            user_id: ID of user performing the deletion
            
        Returns:
            True if successful
            
        Raises:
            NotFoundException: If organization not found
        """
        org = await self.get_organization(org_id)
        
        # Soft delete
        org.is_active = False
        org.deleted_at = datetime.utcnow()
        await self.db.commit()
        
        # Log the action
        await self.audit_service.log_action(
            user_id=user_id,
            organization_id=org_id,
            action="delete",
            resource_type="organization",
            resource_id=org_id
        )
        
        return True
    
    async def list_organizations(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> Tuple[List[Dict], int]:
        """
        List organizations that the user is a member of
        
        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (list of organizations, total count)
        """
        # Get organizations where user is a member
        query = (
            select(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(
                and_(
                    Membership.user_id == user_id,
                    Organization.is_active == True
                )
            )
            .order_by(Organization.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        orgs =  result.scalars().all()
        
        # Get total count
        count_query = (
            select(func.count())
            .select_from(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(
                and_(
                    Membership.user_id == user_id,
                    Organization.is_active == True
                )
            )
        )
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()
        
        # Convert to dict for response
        org_list = [org.to_dict() for org in orgs]
        
        return org_list, total
    
    async def get_user_role(self, user_id: str, org_id: str) -> Optional[MemberRole]:
        """
        Get a user's role in an organization
        
        Args:
            user_id: User ID
            org_id: Organization ID
            
        Returns:
            User's role or None if not a member
        """
        query = (
            select(Membership.role)
            .where(
                and_(
                    Membership.user_id == user_id,
                    Membership.organization_id == org_id
                )
            )
        )
        
        result = await self.db.execute(query)
        role = result.scalar_one_or_none()
        
        return role
    
    async def check_permission(
        self, 
        user_id: str, 
        org_id: str, 
        required_roles: List[MemberRole]
    ) -> bool:
        """
        Check if user has one of the required roles in the organization
        
        Args:
            user_id: User ID
            org_id: Organization ID
            required_roles: List of roles that are allowed
            
        Returns:
            True if user has permission, False otherwise
        """
        # Check if user is superadmin first
        user_query = select(User.is_superadmin).where(User.id == user_id)
        user_result = await self.db.execute(user_query)
        is_superadmin = user_result.scalar_one_or_none()
        
        if is_superadmin:
            return True
            
        # Check organization role
        role = await self.get_user_role(user_id, org_id)
        
        if not role:
            return False
            
        return role in required_roles
    
    async def require_permission(
        self, 
        user_id: str, 
        org_id: str, 
        required_roles: List[MemberRole]
    ) -> None:
        """
        Require that user has one of the specified roles, or raise exception
        
        Args:
            user_id: User ID
            org_id: Organization ID
            required_roles: List of roles that are allowed
            
        Raises:
            ForbiddenException: If user doesn't have permission
        """
        has_permission = await self.check_permission(user_id, org_id, required_roles)
        
        if not has_permission:
            raise ForbiddenException("You don't have permission to perform this action")
    
    async def list_members(
        self, 
        org_id: str, 
        search: Optional[str] = None,
        role: Optional[MemberRole] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0, 
        limit: int = 100
    ) -> Tuple[List[Dict], int]:
        """
        List members of an organization with search and filters
        
        Args:
            org_id: Organization ID
            search: Search term for email or full name
            role: Filter by specific role
            sort_by: Field to sort by (created_at, full_name, email, role)
            sort_order: Sort order (asc or desc)
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (list of members, total count)
        """
        # Base conditions
        conditions = [Membership.organization_id == org_id]
        
        # Apply search filter if provided
        if search:
            search_term = f"%{search.lower()}%"
            conditions.append(
                or_(
                    func.lower(User.email).like(search_term),
                    func.lower(User.full_name).like(search_term)
                )
            )
        
        # Apply role filter if provided
        if role:
            conditions.append(Membership.role == role)
        
        # Determine sort field and direction
        if sort_by == "full_name":
            sort_field = User.full_name
        elif sort_by == "email":
            sort_field = User.email
        elif sort_by == "role":
            sort_field = Membership.role
        else:
            sort_field = Membership.created_at
            
        if sort_order.lower() == "asc":
            sort_expr = sort_field.asc()
        else:
            sort_expr = sort_field.desc()
        
        # Get members with user details
        query = (
            select(Membership, User)
            .join(User, Membership.user_id == User.id)
            .where(*conditions)
            .order_by(sort_expr)
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        members_with_users = result.all()
        
        # Get total count
        count_query = (
            select(func.count())
            .select_from(Membership)
            .join(User, Membership.user_id == User.id)
            .where(*conditions)
        )
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()
        
        # Get inviter details for all members
        inviter_ids = {m.invited_by for m, _ in members_with_users if m.invited_by}
        inviters = {}
        
        if inviter_ids:
            inviter_query = select(User).where(User.id.in_(inviter_ids))
            inviter_result = await self.db.execute(inviter_query)
            inviters = {user.id: user for user in inviter_result.scalars().all()}
        
        # Format response
        members_list = []
        for membership, user in members_with_users:
            inviter = inviters.get(membership.invited_by)
            members_list.append({
                "id": membership.id,
                "user_id": user.id,
                "organization_id": membership.organization_id,
                "email": user.email,
                "full_name": user.full_name,
                "role": membership.role.value,
                "created_at": membership.created_at,
                "invited_by": membership.invited_by,
                "inviter_name": inviter.full_name if inviter else None,
                "invitation_accepted_at": membership.invitation_accepted_at,
                "last_login": user.last_login
            })
        
        return members_list, total
    
    async def update_member_role(
        self, 
        org_id: str, 
        user_id: str, 
        member_id: str, 
        new_role: MemberRole
    ) -> Dict:
        """
        Update a member's role in the organization
        
        Args:
            org_id: Organization ID
            user_id: ID of user making the change
            member_id: ID of the membership to update
            new_role: New role to assign
            
        Returns:
            Updated membership details
            
        Raises:
            NotFoundException: If membership not found
            ForbiddenException: If trying to change the role of the owner
        """
        # Get the membership
        query = (
            select(Membership, User)
            .join(User, Membership.user_id == User.id)
            .where(
                and_(
                    Membership.id == member_id,
                    Membership.organization_id == org_id
                )
            )
        )
        
        result = await self.db.execute(query)
        membership_with_user = result.one_or_none()
        
        if not membership_with_user:
            raise NotFoundException(f"Member with ID {member_id} not found in organization")
            
        membership, user = membership_with_user
        
        # Don't allow changing the owner's role
        if membership.role == MemberRole.OWNER and new_role != MemberRole.OWNER:
            raise ForbiddenException("Cannot change the role of the organization owner")
        
        # Update role
        old_role = membership.role
        membership.role = new_role
        await self.db.commit()
        
        # Log the action
        await self.audit_service.log_action(
            user_id=user_id,
            organization_id=org_id,
            action="update",
            resource_type="membership",
            resource_id=member_id,
            changes={
                "role": {"old": old_role.value, "new": new_role.value}
            }
        )
        
        # Format response
        return {
            "id": membership.id,
            "user_id": user.id,
            "organization_id": membership.organization_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": membership.role.value,
            "created_at": membership.created_at,
            "invited_by": membership.invited_by,
            "invitation_accepted_at": membership.invitation_accepted_at
        }
    
    async def remove_member(
        self, 
        org_id: str, 
        user_id: str, 
        member_user_id: str
    ) -> bool:
        """
        Remove a member from the organization
        
        Args:
            org_id: Organization ID
            user_id: ID of user making the change
            member_user_id: User ID of the member to remove
            
        Returns:
            True if successful
            
        Raises:
            NotFoundException: If membership not found
            ForbiddenException: If trying to remove the owner
        """
        # Get the membership
        query = (
            select(Membership)
            .where(
                and_(
                    Membership.user_id == member_user_id,
                    Membership.organization_id == org_id
                )
            )
        )
        
        result = await self.db.execute(query)
        membership = result.scalar_one_or_none()
        
        if not membership:
            raise NotFoundException(f"User {member_user_id} is not a member of this organization")
            
        # Don't allow removing the owner
        if membership.role == MemberRole.OWNER:
            raise ForbiddenException("Cannot remove the organization owner")
        
        # Delete membership
        await self.db.delete(membership)
        await self.db.commit()
        
        # Log the action
        await self.audit_service.log_action(
            user_id=user_id,
            organization_id=org_id,
            action="delete",
            resource_type="membership",
            resource_id=membership.id
        )
        
        return True
    
    async def invite_member(
        self, 
        org_id: str, 
        inviter_id: str, 
        email: str, 
        role: MemberRole
    ) -> Dict:
        """
        Invite a user to join the organization
        
        Args:
            org_id: Organization ID
            inviter_id: ID of user sending the invitation
            email: Email of the user to invite
            role: Role to assign to the new member
            
        Returns:
            Invitation details
            
        Raises:
            ConflictException: If user is already a member
        """
        # Get organization details
        org = await self.get_organization(org_id)
        
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
                        Membership.organization_id == org_id
                    )
                )
            )
            
            membership_result = await self.db.execute(membership_query)
            existing_membership = membership_result.scalar_one_or_none()
            
            if existing_membership:
                raise ConflictException(f"User {email} is already a member of this organization")
        
        # Get inviter details
        inviter_query = select(User).where(User.id == inviter_id)
        inviter_result = await self.db.execute(inviter_query)
        inviter = inviter_result.scalar_one_or_none()
        
        if not inviter:
            raise NotFoundException("Inviter not found")
        
        # Create membership if user exists, otherwise send invitation
        if user:
            # Create membership directly
            membership = Membership(
                id=str(uuid.uuid4()),
                user_id=user.id,
                organization_id=org_id,
                role=role,
                invited_by=inviter_id
            )
            
            self.db.add(membership)
            await self.db.commit()
            
            # Send notification email
            await self.email_service.send_organization_invitation_notification(
                email=email,
                inviter_name=inviter.full_name,
                organization_name=org.name
            )
            
            # Log the action
            await self.audit_service.log_action(
                user_id=inviter_id,
                organization_id=org_id,
                action="create",
                resource_type="membership",
                resource_id=membership.id,
                changes={"email": email, "role": role.value}
            )
            
            return {
                "id": membership.id,
                "email": email,
                "organization_id": org_id,
                "organization_name": org.name,
                "role": role.value,
                "invited_by": inviter_id,
                "created_at": membership.created_at
            }
        else:
            # TODO: Implement invitation system for non-existing users
            # For now, just return a placeholder
            return {
                "id": str(uuid.uuid4()),
                "email": email,
                "organization_id": org_id,
                "organization_name": org.name,
                "role": role.value,
                "invited_by": inviter_id,
                "created_at": datetime.utcnow(),
                "status": "invitation_pending"
            }
