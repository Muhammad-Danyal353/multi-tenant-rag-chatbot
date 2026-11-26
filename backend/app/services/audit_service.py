"""
Audit Service

This module provides audit logging functionality for tracking user actions
and changes to resources in the system.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func

from app.db.models.audit_log import AuditLog
from app.db.models.user import User

logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for audit logging and tracking user actions.
    """
    
    def __init__(self, db: AsyncSession = None):
        """Initialize the audit service with an optional database session."""
        self.db = db
    
    async def log_action(
        self,
        organization_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None
    ) -> AuditLog:
        """
        Log an action performed by a user.
        
        Args:
            organization_id: Organization ID
            user_id: User ID who performed the action
            action: Action performed (create, update, delete, etc.)
            resource_type: Type of resource affected (bot, knowledge_base, etc.)
            resource_id: ID of the affected resource (optional)
            changes: Dictionary of changes made (old_value, new_value)
            ip_address: IP address of the user (optional)
            met_adata: Additional meta_data about the action (optional)
            db: Database session
            
        Returns:
            Created AuditLog object
        """
        # Create audit log entry
        audit_log = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes or {},
            ip_address=ip_address,
            meta_data=meta_data or {}
        )
        
        # Use provided db session or instance db
        session = db or self.db
        if not session:
            raise ValueError("Database session is required")
            
        session.add(audit_log)
        await session.commit()
        
        return audit_log
    
    async def get_audit_logs(
        self,
        organization_id: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        Get audit logs with filtering and pagination.
        
        Args:
            organization_id: Organization ID
            user_id: Filter by user ID (optional)
            resource_type: Filter by resource type (optional)
            resource_id: Filter by resource ID (optional)
            action: Filter by action (optional)
            start_date: Start date for filtering (ISO format, optional)
            end_date: End date for filtering (ISO format, optional)
            page: Page number for pagination
            page_size: Page size for pagination
            db: Database session
            
        Returns:
            Dict with audit logs and pagination info
        """
        # Validate page parameters
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        
        # Base query conditions
        conditions = [AuditLog.organization_id == organization_id]
        
        # Apply filters
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        
        if resource_id:
            conditions.append(AuditLog.resource_id == resource_id)
        
        if action:
            conditions.append(AuditLog.action == action)
        
        if start_date:
            conditions.append(AuditLog.timestamp >= start_date)
        
        if end_date:
            conditions.append(AuditLog.timestamp <= end_date)
        
        # Count total matching audit logs
        count_stmt = select(func.count()).select_from(AuditLog).where(*conditions)
        result = await db.execute(count_stmt)
        total_count = result.scalar_one()
        
        # Calculate pagination
        offset = (page - 1) * page_size
        has_more = total_count > offset + page_size
        
        # Query audit logs with pagination
        stmt = (
            select(AuditLog)
            .where(*conditions)
            .order_by(desc(AuditLog.timestamp))
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        audit_logs =  result.scalars().all()
        
        # Get user info for audit logs
        user_ids = {log.user_id for log in audit_logs if log.user_id}
        users = {}
        
        if user_ids:
            stmt = select(User).where(User.id.in_(user_ids))
            result = await db.execute(stmt)
            users = {user.id: user for user in  result.scalars().all()}
        
        # Format audit logs with user info
        formatted_logs = []
        for log in audit_logs:
            user = users.get(log.user_id)
            formatted_log = {
                "id": log.id,
                "organization_id": log.organization_id,
                "user_id": log.user_id,
                "user_name": user.full_name if user else None,
                "user_email": user.email if user else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "changes": log.changes,
                "ip_address": log.ip_address,
                "meta_data": log.meta_data,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None
            }
            formatted_logs.append(formatted_log)
        
        # Format response
        return {
            "items": formatted_logs,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": has_more
        }
    
    async def get_user_activity(
        self,
        organization_id: str,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        db: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent activity for a specific user.
        
        Args:
            organization_id: Organization ID
            user_id: User ID
            start_date: Start date for filtering (ISO format, optional)
            end_date: End date for filtering (ISO format, optional)
            limit: Maximum number of activities to return
            db: Database session
            
        Returns:
            List of user activities
        """
        # Base query conditions
        conditions = [
            AuditLog.organization_id == organization_id,
            AuditLog.user_id == user_id
        ]
        
        # Apply date filters
        if start_date:
            conditions.append(AuditLog.timestamp >= start_date)
        
        if end_date:
            conditions.append(AuditLog.timestamp <= end_date)
        
        # Query recent activities
        stmt = (
            select(AuditLog)
            .where(*conditions)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        result = await db.execute(stmt)
        audit_logs =  result.scalars().all()
        
        # Format activities
        activities = []
        for log in audit_logs:
            activity = {
                "id": log.id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "changes": log.changes,
                "ip_address": log.ip_address,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None
            }
            activities.append(activity)
        
        return activities
    
    async def get_resource_history(
        self,
        organization_id: str,
        resource_type: str,
        resource_id: str,
        db: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """
        Get change history for a specific resource.
        
        Args:
            organization_id: Organization ID
            resource_type: Resource type
            resource_id: Resource ID
            db: Database session
            
        Returns:
            List of changes to the resource
        """
        # Query audit logs for the resource
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.organization_id == organization_id,
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id
            )
            .order_by(desc(AuditLog.timestamp))
        )
        result = await db.execute(stmt)
        audit_logs =  result.scalars().all()
        
        # Get user info for audit logs
        user_ids = {log.user_id for log in audit_logs if log.user_id}
        users = {}
        
        if user_ids:
            stmt = select(User).where(User.id.in_(user_ids))
            result = await db.execute(stmt)
            users = {user.id: user for user in  result.scalars().all()}
        
        # Format history
        history = []
        for log in audit_logs:
            user = users.get(log.user_id)
            entry = {
                "id": log.id,
                "user_id": log.user_id,
                "user_name": user.full_name if user else None,
                "action": log.action,
                "changes": log.changes,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None
            }
            history.append(entry)
        
        return history


# Singleton instance
audit_service = AuditService()


def get_audit_service() -> AuditService:
    """
    Dependency injection helper for FastAPI routes.
    Returns the global audit service instance.
    """
    return audit_service
