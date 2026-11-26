"""
Response Utilities

Helper functions for creating standardized API responses.
"""

from typing import TypeVar, Optional, Any
from fastapi.responses import JSONResponse
from app.schemas.base import SuccessResponse, ErrorResponse, MessageResponse, PaginatedResponse, PaginationMeta

T = TypeVar('T')


# ============================================================================
# SUCCESS RESPONSES
# ============================================================================

def create_response(
    data: Any = None,
    message: Optional[str] = None,
    status_code: int = 200
) -> dict:
    """
    Create a standardized response (alias for success_response).
    
    Args:
        data: Response data
        message: Optional success message
        status_code: HTTP status code (default: 200)
        
    Returns:
        dict: Formatted response
        
    Example:
        >>> return create_response(
        ...     data={"id": "123", "name": "John"},
        ...     message="User created successfully",
        ...     status_code=201
        ... )
    """
    return success_response(data, message, status_code)


def success_response(
    data: Any,
    message: Optional[str] = None,
    status_code: int = 200
) -> dict:
    """
    Create a standardized success response.
    
    Args:
        data: Response data
        message: Optional success message
        status_code: HTTP status code (default: 200)
        
    Returns:
        dict: Formatted success response
        
    Example:
        >>> return success_response(
        ...     data={"id": "123", "name": "John"},
        ...     message="User created successfully",
        ...     status_code=201
        ... )
    """
    return {
        "success": True,
        "data": data,
        "message": message,
        "status_code": status_code
    }


def created_response(
    data: Any,
    message: Optional[str] = None
) -> dict:
    """
    Create a 201 Created response.
    
    Args:
        data: Created resource data
        message: Optional success message
        
    Returns:
        dict: Formatted 201 response
    """
    return success_response(data, message, status_code=201)


def message_response(
    message: str,
    status_code: int = 200
) -> dict:
    """
    Create a response with just a message (no data).
    
    Args:
        message: Success message
        status_code: HTTP status code (default: 200)
        
    Returns:
        dict: Formatted message response
        
    Example:
        >>> return message_response("Password reset email sent")
    """
    return {
        "success": True,
        "message": message,
        "status_code": status_code
    }


def paginated_response(
    data: list,
    total: int,
    page: int,
    per_page: int,
    message: Optional[str] = None
) -> dict:
    """
    Create a paginated response.
    
    Args:
        data: List of items for current page
        total: Total number of items
        page: Current page number
        per_page: Items per page
        message: Optional message
        
    Returns:
        dict: Formatted paginated response
    """
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    return {
        "success": True,
        "data": data,
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "message": message,
        "status_code": 200
    }


# ============================================================================
# ERROR RESPONSES
# ============================================================================

def error_response(
    error_code: str,
    message: str,
    status_code: int = 400,
    details: Optional[Any] = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        error_code: Error code (e.g., VALIDATION_ERROR)
        message: Human-readable error message
        status_code: HTTP status code
        details: Optional additional error details
        
    Returns:
        JSONResponse: Formatted error response
        
    Example:
        >>> return error_response(
        ...     error_code="VALIDATION_ERROR",
        ...     message="Email already exists",
        ...     status_code=400
        ... )
    """
    content = {
        "success": False,
        "error": error_code,
        "message": message,
        "status_code": status_code
    }
    
    if details:
        content["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )


def validation_error_response(
    message: str,
    details: Optional[Any] = None
) -> JSONResponse:
    """Create a 422 validation error response."""
    return error_response(
        error_code="VALIDATION_ERROR",
        message=message,
        status_code=422,
        details=details
    )


def not_found_response(
    message: str = "Resource not found"
) -> JSONResponse:
    """Create a 404 not found response."""
    return error_response(
        error_code="NOT_FOUND",
        message=message,
        status_code=404
    )


def unauthorized_response(
    message: str = "Authentication required"
) -> JSONResponse:
    """Create a 401 unauthorized response."""
    return error_response(
        error_code="UNAUTHORIZED",
        message=message,
        status_code=401
    )


def forbidden_response(
    message: str = "Permission denied"
) -> JSONResponse:
    """Create a 403 forbidden response."""
    return error_response(
        error_code="FORBIDDEN",
        message=message,
        status_code=403
    )


def conflict_response(
    message: str = "Resource already exists"
) -> JSONResponse:
    """Create a 409 conflict response."""
    return error_response(
        error_code="CONFLICT",
        message=message,
        status_code=409
    )


def internal_error_response(
    message: str = "An internal error occurred"
) -> JSONResponse:
    """Create a 500 internal server error response."""
    return error_response(
        error_code="INTERNAL_ERROR",
        message=message,
        status_code=500
    )


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "create_response",
    "success_response",
    "created_response",
    "message_response",
    "paginated_response",
    "error_response",
    "validation_error_response",
    "not_found_response",
    "unauthorized_response",
    "forbidden_response",
    "conflict_response",
    "internal_error_response"
]
