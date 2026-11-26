"""
Custom API Exceptions

This module defines custom exceptions for the API.
All exceptions inherit from BaseAPIException which provides consistent error formatting.
"""

from fastapi import status
from typing import Optional, Dict, Any


class BaseAPIException(Exception):
    """
    Base class for all API exceptions.
    
    Attributes:
        status_code: HTTP status code
        detail: Error message
        error_code: Error code for API clients
        headers: Optional HTTP headers
    """
    
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code or self.__class__.__name__
        self.headers = headers


class NotFoundException(BaseAPIException):
    """
    Exception raised when a resource is not found.
    """
    
    def __init__(
        self,
        detail: str = "Resource not found",
        error_code: str = "NOT_FOUND",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            headers=headers
        )


class ValidationError(BaseAPIException):
    """
    Exception raised when request data fails validation.
    """
    
    def __init__(
        self,
        detail: str = "Validation error",
        error_code: str = "VALIDATION_ERROR",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=error_code,
            headers=headers
        )


class AuthenticationError(BaseAPIException):
    """
    Exception raised when authentication fails.
    """
    
    def __init__(
        self,
        detail: str = "Authentication failed",
        error_code: str = "AUTHENTICATION_ERROR",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            headers=headers
        )


class AuthorizationError(BaseAPIException):
    """
    Exception raised when user is not authorized to perform an action.
    """
    
    def __init__(
        self,
        detail: str = "Not authorized to perform this action",
        error_code: str = "AUTHORIZATION_ERROR",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            headers=headers
        )


class RateLimitError(BaseAPIException):
    """
    Exception raised when rate limit is exceeded.
    """
    
    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        error_code: str = "RATE_LIMIT_EXCEEDED",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code=error_code,
            headers=headers
        )


class ConflictException(BaseAPIException):
    """
    Exception raised when there is a conflict with the current state.
    """
    
    def __init__(
        self,
        detail: str = "Conflict with current state",
        error_code: str = "CONFLICT",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_409_CONFLICT,
            error_code=error_code,
            headers=headers
        )


class ServerError(BaseAPIException):
    """
    Exception raised when there is a server-side error.
    """
    
    def __init__(
        self,
        detail: str = "Internal server error",
        error_code: str = "SERVER_ERROR",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            headers=headers
        )


class ForbiddenException(BaseAPIException):
    """
    Exception raised when access to a resource is forbidden.
    """
    
    def __init__(
        self,
        detail: str = "Access forbidden",
        error_code: str = "FORBIDDEN",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            headers=headers
        )


class ExpiredTokenException(BaseAPIException):
    """
    Exception raised when a token has expired.
    """
    
    def __init__(
        self,
        detail: str = "Token has expired",
        error_code: str = "TOKEN_EXPIRED",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            headers=headers
        )


class InvalidTokenException(BaseAPIException):
    """
    Exception raised when a token is invalid.
    """
    
    def __init__(
        self,
        detail: str = "Token is invalid",
        error_code: str = "INVALID_TOKEN",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            headers=headers
        )


class InvalidAPIKeyException(BaseAPIException):
    """
    Exception raised when an API key is invalid.
    """
    
    def __init__(
        self,
        detail: str = "Invalid API key",
        error_code: str = "INVALID_API_KEY",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            headers=headers
        )


class DomainNotAllowedException(BaseAPIException):
    """
    Exception raised when a domain is not in the allowlist.
    """
    
    def __init__(
        self,
        detail: str = "Domain not allowed",
        error_code: str = "DOMAIN_NOT_ALLOWED",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            headers=headers
        )


class TenantAccessDeniedException(BaseAPIException):
    """
    Exception raised when access to a tenant is denied.
    """
    
    def __init__(
        self,
        detail: str = "Tenant access denied",
        error_code: str = "TENANT_ACCESS_DENIED",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            headers=headers
        )


class RateLimitException(BaseAPIException):
    """
    Exception raised when rate limit is exceeded.
    """
    
    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        error_code: str = "RATE_LIMIT_EXCEEDED",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code=error_code,
            headers=headers
        )


class ResourceLimitException(BaseAPIException):
    """
    Exception raised when a resource limit is exceeded.
    """
    
    def __init__(
        self,
        detail: str = "Resource limit exceeded",
        error_code: str = "RESOURCE_LIMIT_EXCEEDED",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            headers=headers
        )


class PaymentRequiredException(BaseAPIException):
    """
    Exception raised when payment is required to proceed.
    """
    
    def __init__(
        self,
        detail: str = "Payment required",
        error_code: str = "PAYMENT_REQUIRED",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            error_code=error_code,
            headers=headers
        )


class ServiceUnavailableException(BaseAPIException):
    """
    Exception raised when a service is unavailable.
    """
    
    def __init__(
        self,
        detail: str = "Service unavailable",
        error_code: str = "SERVICE_UNAVAILABLE",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=error_code,
            headers=headers
        )


class UnauthorizedException(BaseAPIException):
    """
    Exception raised when user is not authorized.
    """
    
    def __init__(
        self,
        detail: str = "Unauthorized access",
        error_code: str = "UNAUTHORIZED",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            headers=headers
        )


class InactiveAccountException(BaseAPIException):
    """
    Exception raised when user account is inactive.
    """
    
    def __init__(
        self,
        detail: str = "Account is inactive",
        error_code: str = "INACTIVE_ACCOUNT",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            headers=headers
        )


class EmailNotVerifiedException(BaseAPIException):
    """
    Exception raised when user email is not verified.
    """
    
    def __init__(
        self,
        detail: str = "Email not verified",
        error_code: str = "EMAIL_NOT_VERIFIED",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            headers=headers
        )


class BotNotFoundException(BaseAPIException):
    """
    Exception raised when a bot is not found.
    """
    
    def __init__(
        self,
        detail: str = "Bot not found",
        error_code: str = "BOT_NOT_FOUND",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            headers=headers
        )


class QdrantException(BaseAPIException):
    """
    Exception raised when there is an error with Qdrant vector database operations.
    """
    
    def __init__(
        self,
        detail: str = "Qdrant operation failed",
        error_code: str = "QDRANT_ERROR",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            headers=headers
        )


class InvalidCredentialsException(BaseAPIException):
    """
    Exception raised when user credentials are invalid.
    """
    
    def __init__(
        self,
        detail: str = "Invalid credentials",
        error_code: str = "INVALID_CREDENTIALS",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            headers=headers
        )


class EmailAlreadyExistsException(BaseAPIException):
    """
    Exception raised when trying to register with an email that already exists.
    """
    
    def __init__(
        self,
        detail: str = "Email already exists",
        error_code: str = "EMAIL_ALREADY_EXISTS",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_409_CONFLICT,
            error_code=error_code,
            headers=headers
        )


class ValidationException(BaseAPIException):
    """
    Exception raised when request data fails validation.
    """
    
    def __init__(
        self,
        detail: str = "Validation failed",
        error_code: str = "VALIDATION_EXCEPTION",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=error_code,
            headers=headers
        )


class DuplicateException(BaseAPIException):
    """
    Exception raised when trying to create a resource that already exists.
    """
    
    def __init__(
        self,
        detail: str = "Resource already exists",
        error_code: str = "DUPLICATE_RESOURCE",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_409_CONFLICT,
            error_code=error_code,
            headers=headers
        )


class ServiceException(BaseAPIException):
    """
    Exception raised when there is a service-level error.
    """
    
    def __init__(
        self,
        detail: str = "Service error occurred",
        error_code: str = "SERVICE_ERROR",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            headers=headers
        )


class ProcessingException(BaseAPIException):
    """
    Exception raised when there is an error during data processing.
    """
    
    def __init__(
        self,
        detail: str = "Processing error occurred",
        error_code: str = "PROCESSING_ERROR",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            headers=headers
        )


class RetrievalException(BaseAPIException):
    """
    Exception raised when there is an error during data retrieval.
    """
    
    def __init__(
        self,
        detail: str = "Retrieval error occurred",
        error_code: str = "RETRIEVAL_ERROR",
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            headers=headers
        )
    
class LLMException(BaseAPIException):
    """Raised when LLM service fails"""
    
    def __init__(self, detail: str = "LLM service failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="LLM_ERROR"
        )

class ExternalServiceException(BaseAPIException):
    """Raised when external service (OpenAI, Qdrant, etc.) fails"""
    
    def __init__(self, service: str = "External service", detail: Optional[str] = None):
        message = detail or f"{service} is currently unavailable"
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=message,
            error_code="EXTERNAL_SERVICE_ERROR"
        )


class OpenAIException(ExternalServiceException):
    """Raised when OpenAI API fails"""
    
    def __init__(self, detail: Optional[str] = None):
        super().__init__(service="OpenAI", detail=detail)



class ChatException(BaseAPIException):
    """Raised when chat processing fails"""
    
    def __init__(self, detail: str = "Chat processing failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="CHAT_ERROR"
        )
class KnowledgeSourceNotFoundException(NotFoundException):
    """Raised when knowledge source is not found"""
    
    def __init__(self):
        super().__init__(detail="Knowledge source not found")




class TenantNotFoundException(BaseAPIException):
    """Raised when organization/tenant is not found"""
    
    def __init__(self, detail: str = "Organization not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code="TENANT_NOT_FOUND"
        )
        

class InvalidFileTypeException(BaseAPIException):
    """Raised when file type is not supported"""
    
    def __init__(self, allowed_types: Optional[str] = None):
        detail = "Invalid file type"
        if allowed_types:
            detail += f". Allowed types: {allowed_types}"
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="INVALID_FILE_TYPE"
        )


class FileTooLargeException(BaseAPIException):
    """Raised when uploaded file exceeds size limit"""
    
    def __init__(self, max_size_mb: int = 30):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB",
            error_code="FILE_TOO_LARGE"
        )


class PlanLimitException(BaseAPIException):
    """Raised when action is not allowed in current plan"""
    
    def __init__(self, detail: str = "This feature is not available in your current plan"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="PLAN_LIMIT"
        )


class QuotaExceededException(BaseAPIException):
    """Raised when user exceeds their plan quota"""
    
    def __init__(self, quota_type: str = "resource", detail: Optional[str] = None):
        message = detail or f"You have exceeded your {quota_type} quota"
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
            error_code="QUOTA_EXCEEDED"
        )

class AlreadyExistsException(BaseAPIException):
    """Raised when trying to create a resource that already exists"""
    
    def __init__(self, resource: str = "Resource", detail: Optional[str] = None):
        message = detail or f"{resource} already exists"
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=message,
            error_code="ALREADY_EXISTS"
        )


# Export all exceptions
__all__ = [
    "BaseAPIException",
    "NotFoundException",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "ConflictException",
    "ServerError",
    "ForbiddenException",
    "ExpiredTokenException",
    "InvalidTokenException",
    "InvalidAPIKeyException",
    "DomainNotAllowedException",
    "TenantAccessDeniedException",
    "RateLimitException",
    "ResourceLimitException",
    "PaymentRequiredException",
    "ServiceUnavailableException",
    "UnauthorizedException",
    "InactiveAccountException",
    "EmailNotVerifiedException",
    "BotNotFoundException",
    "QdrantException",
    "InvalidCredentialsException",
    "EmailAlreadyExistsException",
    "ValidationException",
    "DuplicateException",
    "ServiceException",
    "ProcessingException",
    "RetrievalException",
    "LLMException",
    "ChatException",
    "OpenAIException",
    "ExternalServiceException",
    "KnowledgeSourceNotFoundException",
    "TenantNotFoundException",
    "InvalidFileTypeException",
    "FileTooLargeException",
    "PlanLimitException",
    "QuotaExceededException",
    "AlreadyExistsException"
]