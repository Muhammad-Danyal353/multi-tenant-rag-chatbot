"""
Authentication Routes

Handles user authentication, registration, and password management.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    ResendVerificationRequest,
    UserResponse,
    ChangePasswordRequest
)
from app.schemas.base import ApiResponse, SuccessResponse, MessageResponse
from app.utils.response import (
    success_response,
    created_response,
    message_response,
    create_response
)
from app.services import auth_service
from app.core.dependencies import get_current_user
from app.db.models.user import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# REGISTRATION
# ============================================================================

@router.post(
    "/register",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Register a new user account and create their default organization"
)
async def register(
    data: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user.
    
    - **email**: Valid email address (must be unique)
    - **password**: Password (minimum 6 characters)
    - **full_name**: User's full name
    - **organization_name**: Optional organization name (auto-generated if not provided)
    
    Returns the created user and sends a verification email (if enabled).
    """
    user, organization = await auth_service.register_user(
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        organization_name=data.organization_name,
        db=db
    )
    
    user_data = UserResponse.model_validate(user)
    
    return create_response(
        data={
            "user": user_data.model_dump(),
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "slug": organization.slug
            }
        },
        message="Registration successful. Please check your email to verify your account." if user.is_verified is False else "Registration successful.",
        status_code=201
    )


# ============================================================================
# LOGIN
# ============================================================================

@router.post(
    "/login",
    response_model=ApiResponse[dict],
    summary="User login",
    description="Authenticate user and return JWT tokens"
)
async def login(
    data: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    User login.
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns user data and JWT access/refresh tokens.
    """
    user, tokens = await auth_service.authenticate_user(
        email=data.email,
        password=data.password,
        db=db
    )
    
    user_data = UserResponse.model_validate(user)
    
    return create_response(
        data={
            "user": user_data.model_dump(),
            "tokens": tokens
        },
        message="Login successful"
    )


# ============================================================================
# TOKEN REFRESH
# ============================================================================

@router.post(
    "/refresh",
    response_model=ApiResponse[dict],
    summary="Refresh access token",
    description="Get a new access token using refresh token"
)
async def refresh_token(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token.
    
    - **refresh_token**: Valid refresh token
    
    Returns new access and refresh tokens.
    """
    tokens = await auth_service.refresh_access_token(
        refresh_token=data.refresh_token,
        db=db
    )
    
    return create_response(
        data={"tokens": tokens},
        message="Token refreshed successfully"
    )


# ============================================================================
# LOGOUT
# ============================================================================

@router.post(
    "/logout",
    response_model=ApiResponse[dict],
    summary="User logout",
    description="Logout user (client should discard tokens)"
)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    User logout.
    
    Since we're using JWT tokens (stateless), the actual logout happens on the client side
    by discarding the tokens. This endpoint is mainly for consistency and logging.
    
    For production, you might want to implement token blacklisting with Redis.
    """
    logger.info(f"User logged out: {current_user.email}")
    
    return create_response(
        data=None,
        message="Logged out successfully. Please discard your tokens."
    )


# ============================================================================
# EMAIL VERIFICATION
# ============================================================================

@router.post(
    "/verify-email",
    response_model=ApiResponse[dict],
    summary="Verify email address",
    description="Verify user's email using verification token from email"
)
async def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Verify email with token.
    
    - **token**: Email verification token sent to user's email
    
    Marks the user's email as verified and sends a welcome email.
    """
    user = await auth_service.verify_user_email(
        token=data.token,
        db=db
    )
    
    return create_response(
        data={"email": user.email, "is_verified": True},
        message="Email verified successfully. You can now access all features."
    )


@router.post(
    "/resend-verification",
    response_model=ApiResponse[dict],
    summary="Resend verification email",
    description="Resend verification email to user"
)
async def resend_verification(
    data: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Resend verification email.
    
    - **email**: User's email address
    
    Sends a new verification email with a fresh token.
    """
    await auth_service.resend_verification_email(
        email=data.email,
        db=db
    )
    
    return create_response(
        data=None,
        message="Verification email has been resent. Please check your inbox."
    )


# ============================================================================
# PASSWORD RESET
# ============================================================================

@router.post(
    "/forgot-password",
    response_model=ApiResponse[dict],
    summary="Request password reset",
    description="Send password reset link to user's email"
)
async def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request password reset.
    
    - **email**: User's email address
    
    Sends a password reset link to the email address (if it exists).
    Always returns success for security (doesn't reveal if email exists).
    """
    await auth_service.request_password_reset(
        email=data.email,
        db=db
    )
    
    return create_response(
        data=None,
        message="If the email exists, a password reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=ApiResponse[dict],
    summary="Reset password",
    description="Reset password using token from email"
)
async def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password with token.
    
    - **token**: Password reset token from email
    - **new_password**: New password (minimum 6 characters)
    
    Resets the user's password and invalidates the reset token.
    """
    await auth_service.reset_password(
        token=data.token,
        new_password=data.new_password,
        db=db
    )
    
    return create_response(
        data=None,
        message="Password has been reset successfully. You can now login with your new password."
    )


# ============================================================================
# CHANGE PASSWORD (AUTHENTICATED)
# ============================================================================

@router.post(
    "/change-password",
    response_model=ApiResponse[dict],
    summary="Change password",
    description="Change password for authenticated user"
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change password (authenticated).
    
    - **current_password**: Current password
    - **new_password**: New password (minimum 6 characters)
    
    Requires authentication. Verifies current password before changing.
    """
    await auth_service.change_password(
        user=current_user,
        current_password=data.current_password,
        new_password=data.new_password,
        db=db
    )
    
    return create_response(
        data=None,
        message="Password changed successfully."
    )


# ============================================================================
# CURRENT USER
# ============================================================================

@router.get(
    "/me",
    response_model=ApiResponse[dict],
    summary="Get current user",
    description="Get authenticated user's profile information"
)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile.
    
    Requires authentication (JWT token in Authorization header).
    Returns the authenticated user's information.
    """
    user_data = UserResponse.model_validate(current_user)
    
    return create_response(
        data={"user": user_data.model_dump()},
        message="User profile retrieved successfully"
    )


# ============================================================================
# HEALTH CHECK (for auth service)
# ============================================================================

@router.get(
    "/health",
    response_model=ApiResponse[dict],
    summary="Auth service health check",
    description="Check if authentication service is working"
)
async def auth_health_check():
    """
    Health check endpoint for authentication service.
    """
    return create_response(
        data={
            "service": "authentication",
            "status": "healthy",
            "endpoints": [
                "POST /register",
                "POST /login",
                "POST /refresh",
                "POST /logout",
                "POST /verify-email",
                "POST /resend-verification",
                "POST /forgot-password",
                "POST /reset-password",
                "POST /change-password",
                "GET /me"
            ]
        },
        message="Authentication service is healthy"
    )
