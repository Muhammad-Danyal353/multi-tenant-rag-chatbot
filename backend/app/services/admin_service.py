"""
Admin Service

This module provides services for super admin operations.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from app.db.session import get_db, get_async_db
from app.db.models.user import User
from app.db.models.organization import Organization, Membership, MemberRole
from app.core.exceptions import NotFoundException, ForbiddenException


class AdminService:
    """Service for super admin operations"""
    
    def __init__(self, db: AsyncSession = Depends(get_async_db)):
        self.db = db
    
    async def list_users(
        self,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        is_superadmin: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List users with filters and pagination.
        
        Args:
            search: Optional search by name or email
            is_active: Optional filter by active status
            is_verified: Optional filter by verified status
            is_superadmin: Optional filter by superadmin status
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (list of users, total count)
        """
        # Base conditions
        conditions = []
        
        # Apply search filter if provided
        if search:
            search_term = f"%{search.lower()}%"
            conditions.append(
                or_(
                    func.lower(User.full_name).like(search_term),
                    func.lower(User.email).like(search_term)
                )
            )
        
        # Apply active filter if provided
        if is_active is not None:
            conditions.append(User.is_active == is_active)
        
        # Apply verified filter if provided
        if is_verified is not None:
            conditions.append(User.is_verified == is_verified)
        
        # Apply superadmin filter if provided
        if is_superadmin is not None:
            conditions.append(User.is_superadmin == is_superadmin)
        
        # Determine sort field and direction
        if sort_by == "full_name":
            sort_field = User.full_name
        elif sort_by == "email":
            sort_field = User.email
        elif sort_by == "last_login":
            sort_field = User.last_login
        else:
            sort_field = User.created_at
            
        if sort_order.lower() == "asc":
            sort_expr = sort_field.asc()
        else:
            sort_expr = sort_field.desc()
        
        # Query users
        query = (
            select(User)
            .where(and_(*conditions) if conditions else True)
            .order_by(sort_expr)
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        users =  result.scalars().all()
        
        # Get total count
        count_query = (
            select(func.count())
            .select_from(User)
            .where(and_(*conditions) if conditions else True)
        )
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()
        
        # Format response
        user_list = [user.to_dict() for user in users]
        
        return user_list, total
    
    async def get_user_details(self, user_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with user details
            
        Raises:
            NotFoundException: If user not found
        """
        # Get user
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundException(f"User with ID {user_id} not found")
        
        # Get user's organizations
        orgs_query = (
            select(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(Membership.user_id == user_id)
        )
        
        orgs_result = await self.db.execute(orgs_query)
        organizations = orgs_result.scalars().all()
        
        # Get user's memberships with roles
        memberships_query = (
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(Membership.user_id == user_id)
        )
        
        memberships_result = await self.db.execute(memberships_query)
        memberships_data = []
        
        for membership, org in memberships_result:
            memberships_data.append({
                "organization_id": org.id,
                "organization_name": org.name,
                "role": membership.role.value,
                "created_at": membership.created_at.isoformat() if membership.created_at else None
            })
        
        # Format response
        user_data = user.to_dict()
        user_data["organizations"] = [org.to_dict() for org in organizations]
        user_data["memberships"] = memberships_data
        
        return user_data
    
    async def toggle_user_superadmin(self, user_id: str) -> Dict[str, Any]:
        """
        Toggle superadmin status for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with updated user status
            
        Raises:
            NotFoundException: If user not found
        """
        # Get user
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundException(f"User with ID {user_id} not found")
        
        # Toggle superadmin status
        user.is_superadmin = not user.is_superadmin
        user.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "user_id": user_id,
            "email": user.email,
            "full_name": user.full_name,
            "is_superadmin": user.is_superadmin
        }
    
    async def toggle_user_active(self, user_id: str) -> Dict[str, Any]:
        """
        Toggle active status for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with updated user status
            
        Raises:
            NotFoundException: If user not found
        """
        # Get user
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundException(f"User with ID {user_id} not found")
        
        # Toggle active status
        user.is_active = not user.is_active
        user.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "user_id": user_id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active
        }
    
    async def list_organizations(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        plan: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List organizations with filters and pagination.
        
        Args:
            search: Optional search by name or ID
            status: Optional filter by subscription status
            plan: Optional filter by subscription plan
            is_active: Optional filter by active status
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (list of organizations, total count)
        """
        # Base conditions
        conditions = []
        
        # Apply search filter if provided
        if search:
            search_term = f"%{search.lower()}%"
            conditions.append(
                or_(
                    func.lower(Organization.name).like(search_term),
                    func.lower(Organization.id).like(search_term),
                    func.lower(Organization.slug).like(search_term)
                )
            )
        
        # Apply status filter if provided
        if status:
            conditions.append(Organization.subscription_status == status)
        
        # Apply plan filter if provided
        if plan:
            conditions.append(Organization.subscription_plan == plan)
        
        # Apply active filter if provided
        if is_active is not None:
            conditions.append(Organization.is_active == is_active)
        
        # Determine sort field and direction
        if sort_by == "name":
            sort_field = Organization.name
        elif sort_by == "subscription_plan":
            sort_field = Organization.subscription_plan
        elif sort_by == "subscription_status":
            sort_field = Organization.subscription_status
        else:
            sort_field = Organization.created_at
            
        if sort_order.lower() == "asc":
            sort_expr = sort_field.asc()
        else:
            sort_expr = sort_field.desc()
        
        # Query organizations
        query = (
            select(Organization)
            .where(and_(*conditions) if conditions else True)
            .order_by(sort_expr)
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        orgs =  result.scalars().all()
        
        # Get total count
        count_query = (
            select(func.count())
            .select_from(Organization)
            .where(and_(*conditions) if conditions else True)
        )
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()
        
        # Format response
        org_list = [org.to_dict() for org in orgs]
        
        return org_list, total
    
    async def get_organization_details(self, org_id: str) -> Dict[str, Any]:
        """
        Get detailed information about an organization.
        
        Args:
            org_id: Organization ID
            
        Returns:
            Dict with organization details
            
        Raises:
            NotFoundException: If organization not found
        """
        # Get organization
        query = select(Organization).where(Organization.id == org_id)
        result = await self.db.execute(query)
        org = result.scalar_one_or_none()
        
        if not org:
            raise NotFoundException(f"Organization with ID {org_id} not found")
        
        # Get organization's members
        members_query = (
            select(Membership, User)
            .join(User, Membership.user_id == User.id)
            .where(Membership.organization_id == org_id)
        )
        
        members_result = await self.db.execute(members_query)
        members_data = []
        
        for membership, user in members_result:
            members_data.append({
                "user_id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": membership.role.value,
                "created_at": membership.created_at.isoformat() if membership.created_at else None
            })
        
        # Format response
        org_data = org.to_dict()
        org_data["members"] = members_data
        org_data["member_count"] = len(members_data)
        
        return org_data
    
    async def toggle_organization_active(self, org_id: str) -> Dict[str, Any]:
        """
        Toggle active status for an organization.
        
        Args:
            org_id: Organization ID
            
        Returns:
            Dict with updated organization status
            
        Raises:
            NotFoundException: If organization not found
        """
        # Get organization
        query = select(Organization).where(Organization.id == org_id)
        result = await self.db.execute(query)
        org = result.scalar_one_or_none()
        
        if not org:
            raise NotFoundException(f"Organization with ID {org_id} not found")
        
        # Toggle active status
        org.is_active = not org.is_active
        org.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "organization_id": org_id,
            "name": org.name,
            "is_active": org.is_active
        }
