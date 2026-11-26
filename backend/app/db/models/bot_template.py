"""
Bot Template Model

Represents templates for creating bots.
"""

from sqlalchemy import Column, String, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin
import uuid


class BotTemplate(Base, TimestampMixin):
    """
    Bot template model representing templates for creating bots.
    """
    
    __tablename__ = "bot_templates"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the template"
    )
    
    # Basic Information
    name = Column(
        String(255),
        nullable=False,
        comment="Template name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Template description"
    )
    
    category = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Template category"
    )
    
    # Template Settings
    settings = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Bot behavior settings template"
    )
    
    widget_settings = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Widget appearance settings template"
    )
    
    system_prompt = Column(
        Text,
        nullable=True,
        comment="Template system prompt"
    )
    
    suggested_questions = Column(
        JSON,
        nullable=True,
        default=list,
        comment="Template suggested questions"
    )
    
    # Template Features
    is_featured = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this template is featured"
    )
    
    is_public = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this template is public"
    )
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<BotTemplate(id={self.id}, name={self.name}, category={self.category})>"
    
    def to_dict(self) -> dict:
        """Convert template to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "settings": self.settings,
            "widget_settings": self.widget_settings,
            "system_prompt": self.system_prompt,
            "suggested_questions": self.suggested_questions,
            "is_featured": self.is_featured,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
