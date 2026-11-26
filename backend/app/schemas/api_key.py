from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""
    name: Optional[str] = Field(None, description="Optional name/description for the API key")
    expires_in_days: Optional[int] = Field(None, description="Number of days until the key expires", ge=1)

class APIKeyResponse(BaseModel):
    """Schema for API key response (without the actual key)."""
    id: str
    bot_id: str
    name: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    is_expired: bool
    
    class Config:
        from_attributes = True

class APIKeyDetail(BaseModel):
    """Schema for API key detail including the plain text key (only returned once)."""
    id: str
    bot_id: str
    name: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    key: str  # Plain text key, only returned once

class APIKeyListResponse(BaseModel):
    """Schema for paginated list of API keys."""
    items: List[APIKeyResponse]
    total: int
