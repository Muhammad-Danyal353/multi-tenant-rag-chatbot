"""
Bot Schemas

Pydantic models for bot CRUD operations and validation.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator, HttpUrl, constr
from enum import Enum
from datetime import datetime
import uuid
import re


class BotStatus(str, Enum):
    """Bot status enumeration"""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class BotTone(str, Enum):
    """Bot tone enumeration"""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    TECHNICAL = "technical"
    CASUAL = "casual"
    FORMAL = "formal"


class WidgetPosition(str, Enum):
    """Widget position enumeration"""
    BOTTOM_RIGHT = "bottom-right"
    BOTTOM_LEFT = "bottom-left"
    TOP_RIGHT = "top-right"
    TOP_LEFT = "top-left"


class ColorSchema(BaseModel):
    """Color schema for widget customization"""
    primary: str = Field("#007bff", description="Primary color (hex)")
    secondary: str = Field("#6c757d", description="Secondary color (hex)")
    background: str = Field("#ffffff", description="Background color (hex)")
    text: str = Field("#212529", description="Text color (hex)")
    
    @validator("*")
    def validate_color_hex(cls, v):
        """Validate hex color format"""
        if not re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", v):
            raise ValueError("Color must be a valid hex color code (e.g., #007bff)")
        return v


class WidgetSettings(BaseModel):
    """Widget appearance and behavior settings"""
    colors: ColorSchema = Field(default_factory=ColorSchema)
    position: WidgetPosition = Field(WidgetPosition.BOTTOM_RIGHT, description="Widget position on screen")
    welcome_message: str = Field("Hi! How can I help you today?", description="Welcome message")
    suggested_questions: List[str] = Field(default_factory=list, description="Suggested starter questions")
    chat_icon: str = Field("default", description="Chat icon type")
    show_branding: bool = Field(True, description="Whether to show branding")
    height: str = Field("500px", description="Widget height")
    width: str = Field("350px", description="Widget width")
    auto_open: bool = Field(False, description="Auto open widget on page load")
    z_index: int = Field(10000, description="CSS z-index for widget")


class BotSettings(BaseModel):
    """Bot behavior settings"""
    tone: BotTone = Field(BotTone.PROFESSIONAL, description="Bot conversation tone")
    temperature: float = Field(0.7, description="LLM temperature (0.0-1.0)", ge=0.0, le=1.0)
    max_tokens: int = Field(500, description="Maximum response tokens", ge=1, le=8000)
    model: str = Field("gpt-3.5-turbo", description="LLM model to use")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    confidence_threshold: float = Field(0.7, description="Confidence threshold for responses", ge=0.0, le=1.0)
    fallback_message: Optional[str] = Field(None, description="Message when confidence is below threshold")
    follow_up_questions: bool = Field(False, description="Generate follow-up questions")


class SuggestedQuestion(BaseModel):
    """Suggested question model"""
    text: str = Field(..., description="Question text")
    category: Optional[str] = Field(None, description="Question category")
    display_order: int = Field(0, description="Display order")


class FallbackResponse(BaseModel):
    """Fallback response model"""
    message: str = Field(..., description="Fallback message")
    condition: str = Field("low_confidence", description="When to show this fallback")
    action: Optional[str] = Field(None, description="Action to take (e.g., 'escalate')")


class BotTemplateReference(BaseModel):
    """Reference to a bot template"""
    template_id: str = Field(..., description="Template ID")
    template_name: str = Field(..., description="Template name")


class BotBase(BaseModel):
    """Base bot model with common attributes"""
    name: constr(min_length=1, max_length=255) = Field(..., description="Bot name")
    description: Optional[str] = Field(None, description="Bot description")
    avatar_url: Optional[HttpUrl] = Field(None, description="URL to bot's avatar image")
    status: BotStatus = Field(BotStatus.DRAFT, description="Bot status")
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Bot behavior settings")
    widget_settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Widget appearance settings")
    allowed_domains: Optional[List[str]] = Field(default_factory=list, description="Allowed domains for widget")
    
    @validator("allowed_domains", each_item=True)
    def validate_domain(cls, v):
        """Validate domain format"""
        if not re.match(r"^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid domain format")
        return v


class BotCreate(BotBase):
    """Schema for creating a new bot"""
    pass


class BotUpdate(BaseModel):
    """Schema for updating an existing bot"""
    name: Optional[constr(min_length=1, max_length=255)] = None
    description: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    status: Optional[BotStatus] = None
    settings: Optional[Dict[str, Any]] = None
    widget_settings: Optional[Dict[str, Any]] = None
    allowed_domains: Optional[List[str]] = None
    
    @validator("allowed_domains", each_item=True)
    def validate_domain(cls, v):
        """Validate domain format"""
        if not re.match(r"^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid domain format")
        return v


class BotSettingsUpdate(BaseModel):
    """Schema for updating bot settings"""
    tone: Optional[BotTone] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=8000)
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    fallback_message: Optional[str] = None
    follow_up_questions: Optional[bool] = None


class WidgetSettingsUpdate(BaseModel):
    """Schema for updating widget settings"""
    colors: Optional[ColorSchema] = None
    position: Optional[WidgetPosition] = None
    welcome_message: Optional[str] = None
    suggested_questions: Optional[List[str]] = None
    chat_icon: Optional[str] = None
    show_branding: Optional[bool] = None
    height: Optional[str] = None
    width: Optional[str] = None
    auto_open: Optional[bool] = None
    z_index: Optional[int] = None


class BotResponse(BotBase):
    """Schema for bot response"""
    id: str
    organization_id: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    api_key: Optional[str] = None  # Only returned when generating a new API key
    
    class Config:
        from_attributes = True


class BotDetailResponse(BotResponse):
    """Detailed bot response with statistics"""
    knowledge_source_count: int = 0
    conversation_count: int = 0
    total_messages: int = 0
    average_rating: Optional[float] = None


class BotListResponse(BaseModel):
    """Response for listing bots"""
    bots: List[BotResponse]
    total: int
    limit: int
    offset: int


class APIKeyResponse(BaseModel):
    """Response for API key operations"""
    bot_id: str
    api_key: str
    message: str = "API key generated successfully"


class BotTemplateBase(BaseModel):
    """Base bot template model"""
    name: constr(min_length=1, max_length=255) = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    category: str = Field(..., description="Template category")
    settings: Dict[str, Any] = Field(..., description="Template settings")
    widget_settings: Dict[str, Any] = Field(..., description="Template widget settings")
    system_prompt: str = Field(..., description="Template system prompt")
    suggested_questions: List[str] = Field(default_factory=list, description="Template suggested questions")


class BotTemplateCreate(BotTemplateBase):
    """Schema for creating a bot template"""
    pass


class BotTemplateResponse(BotTemplateBase):
    """Schema for bot template response"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class BotTemplateListResponse(BaseModel):
    """Response for listing bot templates"""
    templates: List[BotTemplateResponse]
    total: int
    limit: int
    offset: int


class BotFromTemplateCreate(BaseModel):
    """Schema for creating a bot from a template"""
    template_id: str = Field(..., description="Template ID")
    name: constr(min_length=1, max_length=255) = Field(..., description="Bot name")
    description: Optional[str] = Field(None, description="Bot description")
    customize_settings: bool = Field(False, description="Whether to customize template settings")


class SuggestedQuestionsUpdate(BaseModel):
    """Schema for updating suggested questions"""
    questions: List[SuggestedQuestion] = Field(..., description="List of suggested questions")


class FallbackResponsesUpdate(BaseModel):
    """Schema for updating fallback responses"""
    responses: List[FallbackResponse] = Field(..., description="List of fallback responses")


class BotCloneRequest(BaseModel):
    """Schema for cloning a bot"""
    name: constr(min_length=1, max_length=255) = Field(..., description="New bot name")
    clone_knowledge_base: bool = Field(True, description="Whether to clone knowledge base")
