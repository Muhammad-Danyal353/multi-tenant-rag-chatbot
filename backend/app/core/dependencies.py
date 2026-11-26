"""
Dependency Injection Functions

FastAPI dependencies for:
- Current user authentication
- Organization/tenant context
- Permission checking
- Role-based access control
"""

from typing import Optional
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, get_async_db
from app.core.security import verify_token, verify_api_key as verify_api_key_hash
from app.core.exceptions import (
    UnauthorizedException,
    ForbiddenException,
    InvalidTokenException,
    InvalidAPIKeyException,
    TenantAccessDeniedException,
    InactiveAccountException,
    EmailNotVerifiedException,
    BotNotFoundException
)
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Security scheme for JWT Bearer token
security = HTTPBearer(auto_error=False)


# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Extract and validate current user ID from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials from Authorization header
        
    Returns:
        str: User ID from token
        
    Raises:
        UnauthorizedException: If no credentials provided
        InvalidTokenException: If token is invalid or expired
        
    Usage:
        @app.get("/protected")
        def protected_route(user_id: str = Depends(get_current_user_id)):
            return {"user_id": user_id}
    """
    if not credentials:
        raise UnauthorizedException("No authentication credentials provided")
    
    token = credentials.credentials
    payload = verify_token(token, token_type="access")
    
    if not payload:
        raise InvalidTokenException()
    
    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenException("Invalid token payload")
    
    return user_id


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current authenticated user from database.
    
    Args:
        user_id: User ID from token
        db: Database session
        
    Returns:
        User: Current user object
        
    Raises:
        UnauthorizedException: If user not found
        InactiveAccountException: If user account is inactive
    """
    from app.db.models.user import User
    from sqlalchemy import select
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise UnauthorizedException("User not found")
    
    if not user.is_active:
        raise InactiveAccountException()
    
    return user


async def get_verified_user(
    user = Depends(get_current_user)
):
    """
    Get current user and ensure email is verified.
    
    Args:
        user: Current user from get_current_user
        
    Returns:
        User: Verified user object
        
    Raises:
        EmailNotVerifiedException: If email is not verified
    """
    if settings.ENABLE_EMAIL_VERIFICATION and not user.is_verified:
        raise EmailNotVerifiedException()
    
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current user if authenticated, None otherwise.
    Useful for endpoints that work for both authenticated and anonymous users.
    
    Args:
        credentials: Optional HTTP Bearer credentials
        db: Database session
        
    Returns:
        Optional[User]: User object if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token, token_type="access")
        
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        from app.db.models.user import User
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
        user = result.scalar_one_or_none()
        return user
        
    except Exception:
        return None


# ============================================================================
# ORGANIZATION/TENANT DEPENDENCIES
# ============================================================================

async def get_current_organization_id(
    user = Depends(get_current_user),
    organization_id: Optional[str] = Header(None, alias="X-Organization-ID")
) -> str:
    """
    Get current organization ID from header or user's default organization.
    
    Args:
        user: Current authenticated user
        organization_id: Organization ID from X-Organization-ID header
        
    Returns:
        str: Organization ID
        
    Raises:
        TenantAccessDeniedException: If user doesn't have access to organization
    """
    from app.db.models.organization import Membership
    from app.db.session import get_db, get_async_db
    
    # If no organization_id in header, get user's first organization
    if not organization_id:
        # This would typically get the user's default or first organization
        # For now, we'll require it in the header
        raise TenantAccessDeniedException("Organization ID required in X-Organization-ID header")
    
    # Verify user has access to this organization
    db = next(get_db())
    try:
        membership = db.query(Membership).filter(
            Membership.user_id == user.id,
            Membership.organization_id == organization_id
        ).first()
        
        if not membership:
            raise TenantAccessDeniedException()
        
        return organization_id
    finally:
        db.close()


async def get_current_organization(
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current organization object.
    
    Args:
        organization_id: Organization ID
        db: Database session
        
    Returns:
        Organization: Current organization object
    """
    from app.db.models.organization import Organization
    from sqlalchemy import select
    
    result = await db.execute(select(Organization).where(
        Organization.id == organization_id,
        Organization.is_active == True
    ))
    org = result.scalar_one_or_none()
    
    if not org:
        raise TenantAccessDeniedException("Organization not found or inactive")
    
    return org


# ============================================================================
# PERMISSION & ROLE DEPENDENCIES
# ============================================================================

class RequirePermission:
    """
    Dependency class to check user permissions.
    
    Usage:
        @app.get("/bots")
        def list_bots(user = Depends(RequirePermission("bot:view"))):
            ...
    """
    
    def __init__(self, permission: str):
        self.permission = permission
    
    async def __call__(
        self,
        user = Depends(get_current_user),
        organization_id: str = Depends(get_current_organization_id),
        db: AsyncSession = Depends(get_async_db)
    ):
        """Check if user has required permission in organization"""
        from app.db.models.organization import Membership
        from sqlalchemy import select
        
        result = await db.execute(select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == organization_id
        ))
        membership = result.scalar_one_or_none()
        
        if not membership:
            raise TenantAccessDeniedException()
        
        # Check permission based on role
        if not self._has_permission(membership.role, self.permission):
            raise ForbiddenException(f"You don't have permission: {self.permission}")
        
        return user
    
    def _has_permission(self, role: str, permission: str) -> bool:
        """Check if role has the required permission"""
        # Super admin has all permissions
        if role == "super_admin":
            return True
        
        # Owner has all organization permissions
        if role == "owner":
            return True
        
        # Define role permissions
        role_permissions = {
            "admin": [
                "bot:*", "kb:*", "member:invite",
                "analytics:view", "chat:view"
            ],
            "member": [
                "bot:create", "bot:edit", "bot:view",
                "kb:manage", "kb:view", "chat:view"
            ],
            "viewer": [
                "bot:view", "kb:view", "analytics:view", "chat:view"
            ]
        }
        
        permissions = role_permissions.get(role, [])
        
        # Check for wildcard permissions
        permission_parts = permission.split(":")
        if len(permission_parts) == 2:
            resource, action = permission_parts
            
            # Check exact match
            if permission in permissions:
                return True
            
            # Check wildcard
            if f"{resource}:*" in permissions:
                return True
        
        return False


class RequireRole:
    """
    Dependency class to check user role.
    
    Usage:
        @app.get("/admin")
        def admin_route(user = Depends(RequireRole(["owner", "admin"]))):
            ...
    """
    
    def __init__(self, roles: list[str]):
        self.roles = roles if isinstance(roles, list) else [roles]
    
    async def __call__(
        self,
        user = Depends(get_current_user),
        organization_id: str = Depends(get_current_organization_id),
        db: AsyncSession = Depends(get_async_db)
    ):
        """Check if user has required role in organization"""
        from app.db.models.organization import Membership
        from sqlalchemy import select
        
        result = await db.execute(select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == organization_id
        ))
        membership = result.scalar_one_or_none()
        
        if not membership:
            raise TenantAccessDeniedException()
        
        if membership.role not in self.roles:
            raise ForbiddenException(
                f"Required role: {', '.join(self.roles)}. Your role: {membership.role}"
            )
        
        return user


# ============================================================================
# SUPER ADMIN DEPENDENCY
# ============================================================================

async def require_super_admin(
    user = Depends(get_current_user)
):
    """
    Require super admin access.
    
    Args:
        user: Current user
        
    Returns:
        User: User object if super admin
        
    Raises:
        ForbiddenException: If user is not super admin
    """
    if not user.is_superadmin:
        raise ForbiddenException("Super admin access required")
    
    return user


# ============================================================================
# API KEY AUTHENTICATION (for widget)
# ============================================================================

async def get_bot_from_api_key(
    api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Authenticate bot using API key (for widget endpoints).
    
    Args:
        api_key: API key from X-API-Key header
        db: Database session
        
    Returns:
        Bot: Bot object
        
    Raises:
        InvalidAPIKeyException: If API key is invalid
    """
    from app.db.models.bot import Bot
    from app.core.security import hash_api_key
    
    if not api_key:
        raise InvalidAPIKeyException("API key required")
    
    # Hash the provided key to compare with stored hash
    api_key_hash = hash_api_key(api_key)
    
    from sqlalchemy import select
    result = await db.execute(select(Bot).where(
        Bot.api_key_hash == api_key_hash,
        Bot.status == "active"
    ))
    bot = result.scalar_one_or_none()
    
    if not bot:
        raise InvalidAPIKeyException()
    
    return bot


# ============================================================================
# DOMAIN VALIDATION (for widget)
# ============================================================================

async def validate_widget_domain(
    origin: Optional[str] = Header(None),
    bot = Depends(get_bot_from_api_key)
):
    """
    Validate that request origin is in bot's allowed domains.
    
    Args:
        origin: Origin header from request
        bot: Bot object from API key
        
    Returns:
        Bot: Bot object if domain is allowed
        
    Raises:
        DomainNotAllowedException: If domain is not in allowed list
    """
    from app.core.exceptions import DomainNotAllowedException
    
    # If no allowed_domains configured, allow all (not recommended for production)
    if not bot.allowed_domains or len(bot.allowed_domains) == 0:
        return bot
    
    if not origin:
        raise DomainNotAllowedException("Origin header required")
    
    # Check if origin matches any allowed domain
    # Support wildcards like *.example.com
    allowed = False
    for allowed_domain in bot.allowed_domains:
        if allowed_domain == "*":
            allowed = True
            break
        if allowed_domain.startswith("*."):
            # Wildcard subdomain
            base_domain = allowed_domain[2:]
            if origin.endswith(base_domain):
                allowed = True
                break
        elif origin == allowed_domain or origin.startswith(f"https://{allowed_domain}") or origin.startswith(f"http://{allowed_domain}"):
            allowed = True
            break
    
    if not allowed:
        raise DomainNotAllowedException()
    
    return bot


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def require_permission(permission: str):
    """
    Convenience function to create a permission dependency.
    
    Args:
        permission: Required permission string (e.g., "bot:create")
        
    Returns:
        Dependency function
        
    Usage:
        @app.get("/bots")
        def list_bots(user = Depends(require_permission("bot:view"))):
            ...
    """
    return RequirePermission(permission)


def require_role(roles: list[str]):
    """
    Convenience function to create a role dependency.
    
    Args:
        roles: List of allowed roles
        
    Returns:
        Dependency function
        
    Usage:
        @app.get("/admin")
        def admin_route(user = Depends(require_role(["owner", "admin"]))):
            ...
    """
    return RequireRole(roles)


async def require_organization(
    user = Depends(get_current_user),
    organization_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Require organization context for the request.
    This is a convenience dependency that combines user authentication
    and organization validation.
    
    Args:
        user: Current authenticated user
        organization_id: Organization ID from X-Organization-ID header
        db: Database session
        
    Returns:
        tuple: (user, organization_id, organization) tuple
        
    Raises:
        TenantAccessDeniedException: If user doesn't have access to organization
        TenantNotFoundException: If organization not found
        
    Usage:
        @app.get("/bots")
        def list_bots(user, org_id, org = Depends(require_organization)):
            ...
    """
    from app.db.models.organization import Organization, Membership
    from app.core.exceptions import TenantNotFoundException
    
    # If no organization_id in header, get user's first organization
    if not organization_id:
        # Get user's first organization
        from sqlalchemy import select
        result = await db.execute(select(Membership).where(
            Membership.user_id == user.id
        ))
        membership = result.scalar_one_or_none()
        
        if not membership:
            raise TenantAccessDeniedException("User is not a member of any organization")
        
        organization_id = membership.organization_id
    
    # Verify user has access to this organization
    from sqlalchemy import select
    result = await db.execute(select(Membership).where(
        Membership.user_id == user.id,
        Membership.organization_id == organization_id
    ))
    membership = result.scalar_one_or_none()
    
    if not membership:
        raise TenantAccessDeniedException()
    
    # Get organization object
    from sqlalchemy import select
    result = await db.execute(select(Organization).where(
        Organization.id == organization_id,
        Organization.is_active == True
    ))
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise TenantNotFoundException()
    
    return user, organization_id, organization


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "get_current_user_id",
    "get_current_user",
    "get_verified_user",
    "get_optional_user",
    "get_current_organization_id",
    "get_current_organization",
    "RequirePermission",
    "RequireRole",
    "require_super_admin",
    "get_bot_from_api_key",
    "validate_widget_domain",
    "require_permission",
    "require_role",
    "require_organization"
]

