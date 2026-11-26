"""
Security Module

Handles all security-related functionality:
- Password hashing and verification
- JWT token generation and validation
- API key generation and validation
- Security utilities
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from app.config import settings
import secrets
import hashlib
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# PASSWORD HASHING
# ============================================================================

# Password context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
        
    Example:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)
        True
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to verify against
        
    Returns:
        bool: True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength based on configured requirements.
    
    Args:
        password: Password to validate
        
    Returns:
        tuple: (is_valid, error_message)
        
    Example:
        >>> validate_password_strength("weak")
        (False, "Password must be at least 8 characters long")
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long"
    
    if settings.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if settings.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if settings.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    if settings.PASSWORD_REQUIRE_SPECIAL:
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain at least one special character"
    
    return True, ""


# ============================================================================
# JWT TOKEN MANAGEMENT
# ============================================================================

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary of data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        str: Encoded JWT token
        
    Example:
        >>> token = create_access_token({"sub": "user@example.com"})
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Dictionary of data to encode in the token
        
    Returns:
        str: Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
        token_type: Expected token type ("access" or "refresh")
        
    Returns:
        Optional[Dict]: Decoded token payload if valid, None otherwise
        
    Example:
        >>> payload = verify_token(token)
        >>> if payload:
        >>>     user_id = payload.get("sub")
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
            return None
        
        return payload
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return None


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without verification (for inspection only).
    
    Args:
        token: JWT token to decode
        
    Returns:
        Optional[Dict]: Decoded token payload if valid, None otherwise
    """
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_signature": False}
        )
    except Exception as e:
        logger.error(f"Token decode error: {str(e)}")
        return None


# ============================================================================
# API KEY MANAGEMENT
# ============================================================================

def generate_api_key() -> str:
    """
    Generate a secure random API key.
    
    Returns:
        str: URL-safe random API key (32 bytes, ~43 characters)
        
    Example:
        >>> api_key = generate_api_key()
        >>> # Returns something like: "rcp_live_abc123XYZ..."
    """
    random_key = secrets.token_urlsafe(32)
    # Add prefix for easy identification
    return f"rcp_live_{random_key}"


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage.
    
    Args:
        api_key: Plain API key to hash
        
    Returns:
        str: SHA-256 hash of the API key
        
    Note:
        Store the hash in the database, not the plain key.
        When validating, hash the provided key and compare hashes.
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash.
    
    Args:
        plain_key: Plain API key to verify
        hashed_key: Hashed API key to verify against
        
    Returns:
        bool: True if keys match, False otherwise
    """
    return hash_api_key(plain_key) == hashed_key


# ============================================================================
# EMAIL VERIFICATION & PASSWORD RESET TOKENS
# ============================================================================

def create_email_verification_token(email: str) -> str:
    """
    Create a token for email verification.
    
    Args:
        email: Email address to verify
        
    Returns:
        str: Verification token
    """
    expire = datetime.utcnow() + timedelta(
        hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
    )
    
    to_encode = {
        "sub": email,
        "exp": expire,
        "type": "email_verification"
    }
    
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def verify_email_token(token: str) -> Optional[str]:
    """
    Verify an email verification token.
    
    Args:
        token: Verification token
        
    Returns:
        Optional[str]: Email address if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        if payload.get("type") != "email_verification":
            return None
        
        return payload.get("sub")
        
    except JWTError:
        return None


def create_password_reset_token(email: str) -> str:
    """
    Create a token for password reset.
    
    Args:
        email: Email address for password reset
        
    Returns:
        str: Password reset token
    """
    expire = datetime.utcnow() + timedelta(
        hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    )
    
    to_encode = {
        "sub": email,
        "exp": expire,
        "type": "password_reset"
    }
    
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token.
    
    Args:
        token: Password reset token
        
    Returns:
        Optional[str]: Email address if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        if payload.get("type") != "password_reset":
            return None
        
        return payload.get("sub")
        
    except JWTError:
        return None


# ============================================================================
# SECURITY UTILITIES
# ============================================================================

def generate_random_string(length: int = 32) -> str:
    """
    Generate a secure random string.
    
    Args:
        length: Length of the random string
        
    Returns:
        str: Random URL-safe string
    """
    return secrets.token_urlsafe(length)


def constant_time_compare(val1: str, val2: str) -> bool:
    """
    Perform a constant-time comparison of two strings.
    Prevents timing attacks.
    
    Args:
        val1: First string
        val2: Second string
        
    Returns:
        bool: True if strings match, False otherwise
    """
    return secrets.compare_digest(val1.encode(), val2.encode())


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "decode_token",
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    "create_email_verification_token",
    "verify_email_token",
    "create_password_reset_token",
    "verify_password_reset_token",
    "generate_random_string",
    "constant_time_compare"
]

