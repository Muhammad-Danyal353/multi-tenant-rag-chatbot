"""
Authentication Service

Business logic for user authentication, registration, and account management.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_
import re

from app.db.models.user import User
from app.db.models.organization import Organization, Membership, MemberRole, SubscriptionPlan, SubscriptionStatus
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    verify_token,
    create_email_verification_token,
    verify_email_token,
    create_password_reset_token,
    verify_password_reset_token
)
from app.core.exceptions import (
    InvalidCredentialsException,
    EmailAlreadyExistsException,
    InvalidTokenException,
    NotFoundException,
    ValidationException,
    InactiveAccountException,
    EmailNotVerifiedException
)
from app.services.email_service import (
    send_verification_email,
    send_password_reset_email,
    send_welcome_email
)
from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_organization_slug(name: str, db: Session) -> str:
    """
    Generate a unique slug for organization from name.
    
    Args:
        name: Organization name
        db: Database session
        
    Returns:
        str: Unique slug
    """
    # Convert to lowercase and replace spaces with hyphens
    base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    
    # Ensure uniqueness
    slug = base_slug
    counter = 1
    
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    return slug


def create_default_organization(user: User, name: str, db: Session) -> Organization:
    """
    Create a default organization for a new user.
    
    Args:
        user: User object
        name: Organization name
        db: Database session
        
    Returns:
        Organization: Created organization
    """
    slug = generate_organization_slug(name, db)
    
    # Create organization
    organization = Organization(
        name=name,
        slug=slug,
        subscription_plan=SubscriptionPlan.FREE,
        subscription_status=SubscriptionStatus.ACTIVE,
        usage_limits=settings.FREE_PLAN_LIMITS,
        is_active=True
    )
    
    db.add(organization)
    db.flush()  # Get the organization ID
    
    # Create membership with owner role
    membership = Membership(
        user_id=user.id,
        organization_id=organization.id,
        role=MemberRole.OWNER
    )
    
    db.add(membership)
    db.commit()
    db.refresh(organization)
    
    logger.info(f"Created default organization '{name}' for user {user.email}")
    
    return organization


# ============================================================================
# REGISTRATION
# ============================================================================

async def register_user(
    email: str,
    password: str,
    full_name: str,
    organization_name: Optional[str],
    db: Session
) -> Tuple[User, Organization]:
    """
    Register a new user and create their organization.
    
    Args:
        email: User email
        password: User password
        full_name: User's full name
        organization_name: Optional organization name
        db: Database session
        
    Returns:
        Tuple[User, Organization]: Created user and organization
        
    Raises:
        EmailAlreadyExistsException: If email already exists
        ValidationException: If validation fails
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == email.lower()).first()
    if existing_user:
        raise EmailAlreadyExistsException()
    
    # Validate password strength
    is_valid, error_message = validate_password_strength(password)
    if not is_valid:
        raise ValidationException(error_message)
    
    # Create user
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name,
        is_active=True,
        is_verified=False if settings.ENABLE_EMAIL_VERIFICATION else True,
        is_superadmin=False
    )
    
    db.add(user)
    db.flush()  # Get the user ID
    
    # Create organization
    org_name = organization_name or f"{full_name}'s Organization"
    organization = create_default_organization(user, org_name, db)
    
    # Generate and save email verification token
    if settings.ENABLE_EMAIL_VERIFICATION:
        verification_token = create_email_verification_token(user.email)
        user.email_verification_token = verification_token
        db.commit()
        
        # Send verification email
        try:
            await send_verification_email(user.email, user.full_name, verification_token)
            logger.info(f"Verification email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")
            # Don't fail registration if email fails
    else:
        db.commit()
    
    db.refresh(user)
    
    logger.info(f"User registered successfully: {user.email}")
    
    return user, organization


# ============================================================================
# LOGIN
# ============================================================================

async def authenticate_user(
    email: str,
    password: str,
    db: Session
) -> Tuple[User, dict]:
    """
    Authenticate user and generate tokens.
    
    Args:
        email: User email
        password: User password
        db: Database session
        
    Returns:
        Tuple[User, dict]: User object and tokens dict
        
    Raises:
        InvalidCredentialsException: If credentials are invalid
        InactiveAccountException: If account is inactive
        EmailNotVerifiedException: If email not verified (when enabled)
    """
    # Find user
    user = db.query(User).filter(User.email == email.lower()).first()
    
    if not user:
        raise InvalidCredentialsException()
    
    # Verify password
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsException()
    
    # Check if account is active
    if not user.is_active:
        raise InactiveAccountException()
    
    # Check if email is verified (if enabled)
    if settings.ENABLE_EMAIL_VERIFICATION and not user.is_verified:
        raise EmailNotVerifiedException()
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    # Generate tokens
    token_data = {"sub": user.id, "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    tokens = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    }
    
    logger.info(f"User logged in successfully: {user.email}")
    
    return user, tokens


# ============================================================================
# TOKEN REFRESH
# ============================================================================

async def refresh_access_token(
    refresh_token: str,
    db: Session
) -> dict:
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_token: Refresh token
        db: Database session
        
    Returns:
        dict: New tokens
        
    Raises:
        InvalidTokenException: If refresh token is invalid
    """
    # Verify refresh token
    payload = verify_token(refresh_token, token_type="refresh")
    
    if not payload:
        raise InvalidTokenException("Invalid refresh token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenException("Invalid token payload")
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or not user.is_active:
        raise InvalidTokenException("User not found or inactive")
    
    # Generate new tokens
    token_data = {"sub": user.id, "email": user.email}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    
    tokens = {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
    
    logger.info(f"Token refreshed for user: {user.email}")
    
    return tokens


# ============================================================================
# EMAIL VERIFICATION
# ============================================================================

async def verify_user_email(
    token: str,
    db: Session
) -> User:
    """
    Verify user's email using verification token.
    
    Args:
        token: Email verification token
        db: Database session
        
    Returns:
        User: Verified user
        
    Raises:
        InvalidTokenException: If token is invalid
        NotFoundException: If user not found
    """
    # Verify token
    email = verify_email_token(token)
    
    if not email:
        raise InvalidTokenException("Invalid or expired verification token")
    
    # Find user
    user = db.query(User).filter(User.email == email.lower()).first()
    
    if not user:
        raise NotFoundException("User", "User not found")
    
    # Check if already verified
    if user.is_verified:
        logger.info(f"User {user.email} already verified")
        return user
    
    # Update user
    user.is_verified = True
    user.email_verification_token = None
    db.commit()
    db.refresh(user)
    
    # Send welcome email
    try:
        await send_welcome_email(user.email, user.full_name)
        logger.info(f"Welcome email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
    
    logger.info(f"Email verified for user: {user.email}")
    
    return user


async def resend_verification_email(
    email: str,
    db: Session
) -> bool:
    """
    Resend verification email to user.
    
    Args:
        email: User email
        db: Database session
        
    Returns:
        bool: True if sent successfully
        
    Raises:
        NotFoundException: If user not found
        ValidationException: If email already verified
    """
    # Find user
    user = db.query(User).filter(User.email == email.lower()).first()
    
    if not user:
        # Don't reveal if email exists or not for security
        logger.warning(f"Resend verification attempted for non-existent email: {email}")
        return True
    
    # Check if already verified
    if user.is_verified:
        raise ValidationException("Email is already verified")
    
    # Generate new token
    verification_token = create_email_verification_token(user.email)
    user.email_verification_token = verification_token
    db.commit()
    
    # Send email
    await send_verification_email(user.email, user.full_name, verification_token)
    
    logger.info(f"Verification email resent to {user.email}")
    
    return True


# ============================================================================
# PASSWORD RESET
# ============================================================================

async def request_password_reset(
    email: str,
    db: Session
) -> bool:
    """
    Send password reset email.
    
    Args:
        email: User email
        db: Database session
        
    Returns:
        bool: True (always, for security)
    """
    # Find user
    user = db.query(User).filter(User.email == email.lower()).first()
    
    if not user:
        # Don't reveal if email exists or not for security
        logger.warning(f"Password reset requested for non-existent email: {email}")
        return True
    
    # Generate reset token
    reset_token = create_password_reset_token(user.email)
    user.reset_password_token = reset_token
    user.reset_password_token_expires = datetime.utcnow() + timedelta(
        hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    )
    db.commit()
    
    # Send email
    await send_password_reset_email(user.email, user.full_name, reset_token)
    
    logger.info(f"Password reset email sent to {user.email}")
    
    return True


async def reset_password(
    token: str,
    new_password: str,
    db: Session
) -> bool:
    """
    Reset user password using reset token.
    
    Args:
        token: Password reset token
        new_password: New password
        db: Database session
        
    Returns:
        bool: True if reset successful
        
    Raises:
        InvalidTokenException: If token is invalid
        ValidationException: If password validation fails
    """
    # Verify token
    email = verify_password_reset_token(token)
    
    if not email:
        raise InvalidTokenException("Invalid or expired reset token")
    
    # Find user
    user = db.query(User).filter(User.email == email.lower()).first()
    
    if not user:
        raise NotFoundException("User", "User not found")
    
    # Check if token matches and not expired
    if user.reset_password_token != token:
        raise InvalidTokenException("Invalid reset token")
    
    if user.reset_password_token_expires and user.reset_password_token_expires < datetime.utcnow():
        raise InvalidTokenException("Reset token has expired")
    
    # Validate new password
    is_valid, error_message = validate_password_strength(new_password)
    if not is_valid:
        raise ValidationException(error_message)
    
    # Update password
    user.hashed_password = hash_password(new_password)
    user.reset_password_token = None
    user.reset_password_token_expires = None
    db.commit()
    
    logger.info(f"Password reset successfully for user: {user.email}")
    
    return True


# ============================================================================
# PASSWORD CHANGE (authenticated)
# ============================================================================

async def change_password(
    user: User,
    current_password: str,
    new_password: str,
    db: Session
) -> bool:
    """
    Change user password (when authenticated).
    
    Args:
        user: Current user
        current_password: Current password
        new_password: New password
        db: Database session
        
    Returns:
        bool: True if changed successfully
        
    Raises:
        InvalidCredentialsException: If current password is incorrect
        ValidationException: If new password validation fails
    """
    # Verify current password
    if not verify_password(current_password, user.hashed_password):
        raise InvalidCredentialsException("Current password is incorrect")
    
    # Validate new password
    is_valid, error_message = validate_password_strength(new_password)
    if not is_valid:
        raise ValidationException(error_message)
    
    # Update password
    user.hashed_password = hash_password(new_password)
    db.commit()
    
    logger.info(f"Password changed for user: {user.email}")
    
    return True


# ============================================================================
# USER PROFILE
# ============================================================================

async def update_user_profile(
    user: User,
    full_name: Optional[str],
    db: Session
) -> User:
    """
    Update user profile.
    
    Args:
        user: Current user
        full_name: New full name
        db: Database session
        
    Returns:
        User: Updated user
    """
    if full_name:
        user.full_name = full_name.strip()
    
    db.commit()
    db.refresh(user)
    
    logger.info(f"Profile updated for user: {user.email}")
    
    return user


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "register_user",
    "authenticate_user",
    "refresh_access_token",
    "verify_user_email",
    "resend_verification_email",
    "request_password_reset",
    "reset_password",
    "change_password",
    "update_user_profile"
]

