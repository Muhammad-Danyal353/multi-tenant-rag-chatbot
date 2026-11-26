"""
Organization Schemas

This module contains Pydantic models for organization-related data validation.
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from uuid import UUID

# Enums for organization-related schemas
class MemberRoleEnum(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"

class SubscriptionPlanEnum(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"

# Base schemas
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    
class OrganizationCreate(OrganizationBase):
    """Schema for creating a new organization"""
    slug: Optional[str] = Field(None, min_length=3, max_length=255)
    
    @validator('slug', pre=True)
    def validate_slug(cls, v, values):
        """Generate slug from name if not provided"""
        if not v and 'name' in values:
            # Convert name to lowercase, replace spaces with hyphens, and remove special chars
            import re
            slug = re.sub(r'[^a-z0-9-]', '', values['name'].lower().replace(' ', '-'))
            return slug
        return v

class OrganizationSettingsSchema(BaseModel):
    """Schema for organization settings"""
    branding: Optional[Dict[str, Any]] = Field(
        None,
        description="Branding settings (colors, logo URL, etc.)"
    )
    default_bot_settings: Optional[Dict[str, Any]] = Field(
        None,
        description="Default settings for new bots"
    )
    notification_preferences: Optional[Dict[str, bool]] = Field(
        None,
        description="Notification preferences"
    )
    security: Optional[Dict[str, Any]] = Field(
        None,
        description="Security settings"
    )
    custom_domain: Optional[str] = Field(
        None,
        description="Custom domain for organization"
    )

class OrganizationUpdate(BaseModel):
    """Schema for updating an existing organization"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    settings: Optional[OrganizationSettingsSchema] = None
    is_active: Optional[bool] = None

class OrganizationResponse(OrganizationBase):
    """Schema for organization response"""
    id: str
    slug: str
    subscription_plan: SubscriptionPlanEnum
    subscription_status: SubscriptionStatusEnum
    settings: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Member schemas
class MemberBase(BaseModel):
    """Base schema for organization member"""
    role: MemberRoleEnum

class MemberCreate(MemberBase):
    """Schema for adding a member to an organization"""
    email: EmailStr
    
class MemberUpdate(BaseModel):
    """Schema for updating a member's role"""
    role: MemberRoleEnum

class MemberResponse(MemberBase):
    """Schema for member response"""
    id: str
    user_id: str
    organization_id: str
    email: str
    full_name: str
    role: MemberRoleEnum
    created_at: datetime
    invited_by: Optional[str] = None
    invitation_accepted_at: Optional[str] = None
    
    class Config:
        from_attributes = True

# Invitation schemas
class InvitationCreate(BaseModel):
    """Schema for creating a new invitation"""
    email: EmailStr
    role: MemberRoleEnum = MemberRoleEnum.MEMBER

class InvitationResponse(BaseModel):
    """Schema for invitation response"""
    id: str
    email: str
    organization_id: str
    organization_name: str
    role: MemberRoleEnum
    invited_by: str
    created_at: datetime
    expires_at: datetime
    is_expired: bool
    is_accepted: bool
    
    class Config:
        from_attributes = True
        
class InvitationAccept(BaseModel):
    """Schema for accepting an invitation"""
    token: str
    
class InvitationListResponse(BaseModel):
    """Schema for list of invitations"""
    items: List[InvitationResponse]
    total: int
    
    class Config:
        from_attributes = True

# List responses
class OrganizationListResponse(BaseModel):
    """Schema for list of organizations"""
    items: List[OrganizationResponse]
    total: int
    
    class Config:
        from_attributes = True

class MemberListResponse(BaseModel):
    """Schema for list of members"""
    items: List[MemberResponse]
    total: int
    
    class Config:
        from_attributes = True
