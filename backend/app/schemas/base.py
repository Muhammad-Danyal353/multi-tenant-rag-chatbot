"""
Base Schemas

Standard response formats and base models for the API.
"""

from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field


# Generic type for response data
T = TypeVar('T')


# ============================================================================
# STANDARD API RESPONSE
# ============================================================================

class ApiResponse(BaseModel, Generic[T]):
    """
    Standard API response format for all endpoints.
    
    Provides consistent structure for success and error responses.
    
    Example success response:
    ```json
    {
        "success": true,
        "data": {"id": "123", "name": "John"},
        "message": "User created successfully",
        "status_code": 201
    }
    ```
    
    Example error response:
    ```json
    {
        "success": false,
        "error": "VALIDATION_ERROR",
        "message": "Email already exists",
        "status_code": 400
    }
    ```
    """
    
    success: bool = Field(
        ...,
        description="Whether the request was successful"
    )
    
    data: Optional[T] = Field(
        default=None,
        description="Response data (null on error)"
    )
    
    message: Optional[str] = Field(
        default=None,
        description="Success or error message"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error code (only present on errors)"
    )
    
    status_code: int = Field(
        ...,
        description="HTTP status code"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": "123", "email": "user@example.com"},
                "message": "Operation completed successfully",
                "status_code": 200
            }
        }


class SuccessResponse(BaseModel, Generic[T]):
    """
    Success response wrapper.
    
    Use this for successful operations.
    """
    
    success: bool = Field(
        default=True,
        description="Always true for success responses"
    )
    
    data: T = Field(
        ...,
        description="Response data"
    )
    
    message: Optional[str] = Field(
        default=None,
        description="Success message"
    )
    
    status_code: int = Field(
        default=200,
        description="HTTP status code"
    )


class ErrorResponse(BaseModel):
    """
    Error response wrapper.
    
    Use this for error responses.
    """
    
    success: bool = Field(
        default=False,
        description="Always false for error responses"
    )
    
    error: str = Field(
        ...,
        description="Error code (e.g., VALIDATION_ERROR, NOT_FOUND)"
    )
    
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    
    details: Optional[Any] = Field(
        default=None,
        description="Additional error details (e.g., validation errors)"
    )
    
    status_code: int = Field(
        ...,
        description="HTTP status code"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "Invalid input data",
                "details": {"email": ["Email already exists"]},
                "status_code": 400
            }
        }


class MessageResponse(BaseModel):
    """
    Simple message response (for operations that don't return data).
    """
    
    success: bool = Field(
        default=True,
        description="Whether the operation was successful"
    )
    
    message: str = Field(
        ...,
        description="Response message"
    )
    
    status_code: int = Field(
        default=200,
        description="HTTP status code"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "status_code": 200
            }
        }


# ============================================================================
# PAGINATION
# ============================================================================

class PaginationMeta(BaseModel):
    """Pagination metadata"""
    
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there's a next page")
    has_prev: bool = Field(..., description="Whether there's a previous page")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Paginated response wrapper.
    
    Use this for list endpoints with pagination.
    """
    
    success: bool = Field(default=True)
    data: list[T] = Field(..., description="List of items")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
    message: Optional[str] = None
    status_code: int = Field(default=200)


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "ApiResponse",
    "SuccessResponse",
    "ErrorResponse",
    "MessageResponse",
    "PaginatedResponse",
    "PaginationMeta"
]

