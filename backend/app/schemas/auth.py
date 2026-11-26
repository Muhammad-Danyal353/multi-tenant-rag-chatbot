"""
Authentication Schemas

Pydantic models for authentication requests and responses.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime


# ============================================================================
# REGISTRATION SCHEMAS
# ============================================================================

class UserRegisterRequest(BaseModel):
    """Schema for user registration request"""
    
    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"]
    )
    
    password: str = Field(
        ...,
        min_length=6,
        description="User's password (min 6 characters)",
        examples=["SecurePassword123"]
    )
    
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="User's full name",
        examples=["John Doe"]
    )
    
    organization_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=255,
        description="Optional organization name (will create new organization if provided)",
        examples=["Acme Corp"]
    )
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        """Validate full name doesn't contain only whitespace"""
        if not v or not v.strip():
            raise ValueError("Full name cannot be empty or only whitespace")
        return v.strip()


class UserRegisterResponse(BaseModel):
    """Schema for successful registration response"""
    
    id: str
    email: str
    full_name: str
    is_verified: bool
    created_at: datetime
    message: str = "Registration successful. Please check your email to verify your account."
    
    class Config:
        from_attributes = True


# ============================================================================
# LOGIN SCHEMAS
# ============================================================================

class UserLoginRequest(BaseModel):
    """Schema for user login request"""
    
    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"]
    )
    
    password: str = Field(
        ...,
        description="User's password",
        examples=["SecurePassword123"]
    )


class TokenResponse(BaseModel):
    """Schema for token response"""
    
    access_token: str = Field(
        ...,
        description="JWT access token"
    )
    
    refresh_token: str = Field(
        ...,
        description="JWT refresh token"
    )
    
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')"
    )
    
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds"
    )



# ============================================================================
# TOKEN SCHEMAS
# ============================================================================

class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request"""
    
    refresh_token: str = Field(
        ...,
        description="Refresh token to exchange for new access token"
    )


class RefreshTokenResponse(BaseModel):
    """Schema for token refresh response"""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# ============================================================================
# PASSWORD RESET SCHEMAS
# ============================================================================

class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request"""
    
    email: EmailStr = Field(
        ...,
        description="Email address to send password reset link",
        examples=["user@example.com"]
    )


class ForgotPasswordResponse(BaseModel):
    """Schema for forgot password response"""
    
    message: str = "If the email exists, a password reset link has been sent."


class ResetPasswordRequest(BaseModel):
    """Schema for password reset request"""
    
    token: str = Field(
        ...,
        description="Password reset token from email"
    )
    
    new_password: str = Field(
        ...,
        min_length=6,
        description="New password (min 6 characters)",
        examples=["NewSecurePassword123"]
    )


class ResetPasswordResponse(BaseModel):
    """Schema for password reset response"""
    
    message: str = "Password has been reset successfully. You can now login with your new password."


# ============================================================================
# EMAIL VERIFICATION SCHEMAS
# ============================================================================

class VerifyEmailRequest(BaseModel):
    """Schema for email verification request"""
    
    token: str = Field(
        ...,
        description="Email verification token from email link"
    )


class VerifyEmailResponse(BaseModel):
    """Schema for email verification response"""
    
    message: str = "Email verified successfully. You can now access all features."
    email: str


class ResendVerificationRequest(BaseModel):
    """Schema for resend verification email request"""
    
    email: EmailStr = Field(
        ...,
        description="Email address to resend verification link",
        examples=["user@example.com"]
    )


class ResendVerificationResponse(BaseModel):
    """Schema for resend verification response"""
    
    message: str = "Verification email has been resent. Please check your inbox."


# ============================================================================
# USER SCHEMAS
# ============================================================================

class UserResponse(BaseModel):
    """Schema for user data in responses"""
    
    id: str
    email: str
    full_name: str
    is_active: bool
    is_verified: bool
    is_superadmin: bool
    last_login: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserLoginResponse(BaseModel):
    """Schema for successful login response"""
    
    user: UserResponse
    tokens: TokenResponse


class UserUpdateRequest(BaseModel):
    """Schema for updating user profile"""
    
    full_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=255,
        description="User's full name"
    )
    
    current_password: Optional[str] = Field(
        None,
        description="Current password (required if changing password)"
    )
    
    new_password: Optional[str] = Field(
        None,
        min_length=6,
        description="New password (min 6 characters)"
    )
    
    @field_validator('new_password')
    @classmethod
    def validate_password_change(cls, v, values):
        """If new_password is provided, current_password must also be provided"""
        if v and not values.data.get('current_password'):
            raise ValueError("current_password is required when changing password")
        return v


class ChangePasswordRequest(BaseModel):
    """Schema for changing password (when authenticated)"""
    
    current_password: str = Field(
        ...,
        description="Current password"
    )
    
    new_password: str = Field(
        ...,
        min_length=6,
        description="New password (min 6 characters)"
    )


class ChangePasswordResponse(BaseModel):
    """Schema for password change response"""
    
    message: str = "Password changed successfully."


# ============================================================================
# LOGOUT SCHEMA
# ============================================================================

class LogoutResponse(BaseModel):
    """Schema for logout response"""
    
    message: str = "Logged out successfully."


# ============================================================================
# ERROR RESPONSES
# ============================================================================

class ErrorResponse(BaseModel):
    """Schema for error responses"""
    
    error: str
    detail: str
    status_code: int


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "UserRegisterRequest",
    "UserRegisterResponse",
    "UserLoginRequest",
    "UserLoginResponse",
    "TokenResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
    "ResetPasswordRequest",
    "ResetPasswordResponse",
    "VerifyEmailRequest",
    "VerifyEmailResponse",
    "ResendVerificationRequest",
    "ResendVerificationResponse",
    "UserResponse",
    "UserUpdateRequest",
    "ChangePasswordRequest",
    "ChangePasswordResponse",
    "LogoutResponse",
    "ErrorResponse"
]

